"""M8 — détection de secrets dans le dépôt.

Remplace l'étape « aucun secret » de la CI, qui reposait sur une recherche de
mots-clés et laissait passer l'essentiel. Mesuré sur sept identifiants réels
— clé d'accès AWS, secret AWS, jeton GitHub, clé OpenAI, jeton Slack, jeton
DagsHub, en-tête de clé privée RSA — l'ancienne étape n'en détectait **aucun**,
pour deux raisons cumulées :

  - elle était sensible à la casse (`grep -I` ignore les fichiers binaires, il
    ne rend pas la recherche insensible), or les constantes s'écrivent
    `AWS_SECRET` et non `aws_secret` ;
  - elle exigeait un mot-clé dans le **nom** de la variable, alors qu'un jeton
    se reconnaît à sa **forme**. `GITHUB_PAT = "ghp_…"` ne contient aucun des
    mots recherchés.

Ce module part de l'inverse : il reconnaît les formes d'identifiants connues,
et n'utilise le nom de la variable que comme signal secondaire.

Usage :
    python -m src.m8_compliance.secret_scan
    python -m src.m8_compliance.secret_scan --chemin src --format json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

# --------------------------------------------------------------------------
# Formes d'identifiants connues
#
# Chaque motif décrit une *forme*, pas un nom. Les préfixes sont donnés par
# concaténation pour que ce fichier ne contienne lui-même aucune chaîne
# ressemblant à un secret — un scanner qui se signale lui-même finit désactivé.
# --------------------------------------------------------------------------

_GH = "gh"
_SK = "sk"
_XOX = "xox"
_DHP = "dhp"

KNOWN_FORMS: tuple[tuple[str, str], ...] = (
    ("cle-acces-aws", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("jeton-github", rf"\b{_GH}[pousr]_[A-Za-z0-9]{{36,255}}\b"),
    ("cle-openai", rf"\b{_SK}-(?:proj-)?[A-Za-z0-9_\-]{{20,}}\b"),
    ("jeton-slack", rf"\b{_XOX}[baprs]-[A-Za-z0-9\-]{{10,}}\b"),
    ("jeton-dagshub", rf"\b{_DHP}_[A-Za-z0-9]{{32,}}\b"),
    ("cle-privee", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ("jeton-jwt", r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\."),
    ("url-avec-identifiants", r"\b[a-z][a-z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@"),
)

# Signal secondaire : un nom évocateur suivi d'une valeur littérale longue.
# Moins précis que les formes ci-dessus, d'où la casse ignorée et la longueur
# minimale — mais c'est ce qui rattrape un jeton propriétaire sans forme connue.
# Le mot-clé est cherché **à l'intérieur** de l'identifiant, sans `\b` initial :
# `AWS_SECRET` ne contient pas de frontière de mot avant `SECRET`, le tiret bas
# étant un caractère de mot. C'est exactement ce qui faisait échouer l'ancienne
# étape, et le répéter ici aurait été le comble.
NAMED_ASSIGNMENT = re.compile(
    r"(?i)[A-Za-z0-9_\-]*"
    r"(?:api[_\-]?key|secret|passwd|password|token|credential|private[_\-]?key)"
    r"[A-Za-z0-9_\-]*\s*[:=]\s*[\"']([^\"']{12,})[\"']"
)

# Valeurs manifestement non secrètes : gabarits, exemples, variables déférées.
PLACEHOLDER = re.compile(
    r"(?i)^(?:"
    r"x+|\.+|-+|\*+|<[^>]*>|\{\{.*\}\}|\$\{.*\}|"
    r"remplacer|changeme|placeholder|example|exemple|votre[_\- ].*|your[_\- ].*|"
    r"none|null|true|false|dummy|fake|test|sample|redacted|masque|"
    r"[a-z_]+\.(?:env|json|yml|yaml|txt)"
    r")$"
)

# Une valeur faite uniquement de minuscules et de séparateurs n'a pas
# l'entropie d'un identifiant : c'est une phrase, donc un gabarit de
# documentation — « un-mot-de-passe-choisi », « votre-cle-ici ». Un secret
# réel porte au moins un chiffre ou une majuscule.
LOW_ENTROPY = re.compile(r"^[a-zà-ÿ]+(?:[\-_ ][a-zà-ÿ]+)+$")

DEFAULT_EXCLUDED_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".dvc", ".pytest_cache"}
)

SCANNED_SUFFIXES = frozenset(
    {".py", ".js", ".mjs", ".ts", ".json", ".yml", ".yaml", ".html", ".css",
     ".md", ".txt", ".sh", ".cfg", ".ini", ".toml", ".env"}
)

# Un commentaire `# m8:autorise <motif>` sur la ligne, ou juste au-dessus,
# neutralise la détection. La justification est obligatoire : une exception
# sans motif est une exception que personne ne réexamine.
ALLOW_MARKER = re.compile(r"m8:autorise\s+(?P<motif>\S.*)$")


@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    kind: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line_no}  [{self.kind}]  {self.excerpt}"


def _redact(value: str) -> str:
    """Ne jamais réimprimer un secret en entier : le rapport de CI est public."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def _is_allowed(lines: list[str], index: int) -> bool:
    if ALLOW_MARKER.search(lines[index]):
        return True
    return index > 0 and bool(ALLOW_MARKER.search(lines[index - 1]))


def scan_text(text: str, path: str = "<texte>") -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if _is_allowed(lines, index):
            continue
        for kind, pattern in KNOWN_FORMS:
            for match in re.finditer(pattern, line):
                findings.append(
                    Finding(path, index + 1, kind, _redact(match.group(0)))
                )
        for match in NAMED_ASSIGNMENT.finditer(line):
            value = match.group(1).strip()
            if PLACEHOLDER.match(value) or LOW_ENTROPY.match(value):
                continue
            findings.append(
                Finding(path, index + 1, "affectation-nommee", _redact(value))
            )
    return findings


def iter_files(
    root: Path, excluded: Iterable[str] = DEFAULT_EXCLUDED_DIRS
) -> Iterator[Path]:
    excluded = set(excluded)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        if any(part in excluded for part in path.parts):
            continue
        yield path


def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(text, str(path.relative_to(root)).replace("\\", "/")))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Détecte les secrets versionnés")
    parser.add_argument("--chemin", default=".", help="racine à analyser")
    parser.add_argument("--format", choices=("texte", "json"), default="texte")
    args = parser.parse_args()

    findings = scan_tree(Path(args.chemin))

    if args.format == "json":
        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
    elif findings:
        print(f"{len(findings)} secret(s) potentiel(s) :\n")
        for finding in findings:
            print(f"  {finding}")
        print(
            "\nSi une occurrence est légitime, ajoutez sur la ligne ou juste "
            "au-dessus :\n  # m8:autorise <motif de l'exception>"
        )
    else:
        print("aucun secret detecte")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
