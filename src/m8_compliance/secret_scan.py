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
_MOTS_CLES = (
    r"(?:api[_\-]?key|secret|passwd|password|token|credential|private[_\-]?key)"
)

NAMED_ASSIGNMENT = re.compile(
    r"(?i)[A-Za-z0-9_\-]*" + _MOTS_CLES + r"[A-Za-z0-9_\-]*"
    r"\s*[:=]\s*[\"']([^\"']{12,})[\"']"
)

# La même chose, mais **valeur nue**, et réservée aux formats de configuration.
#
# La version initiale n'acceptait que la forme entre guillemets — celle du
# Python, du JS et du YAML cité. Elle ratait donc toute la famille des fichiers
# de configuration, où l'on écrit `password = valeur` sans rien autour : c'est
# exactement la forme de `.dvc/config`, de `.gitconfig` et de tout `.ini`.
#
# Restreinte à ces formats, et non appliquée partout : essayée sur l'ensemble
# du dépôt, elle a produit six faux positifs dans le code de M2 — `_TOKEN_RE =
# re.compile(...)`, `getattr(...)`. En Python, la partie droite non citée est
# une expression, jamais un secret ; dans un `.ini`, c'est l'inverse. Le format
# du fichier décide, et c'est le seul discriminant qui tienne.
NAMED_ASSIGNMENT_NU = re.compile(
    r"(?i)^[^\S\n]*[A-Za-z0-9_\-]*" + _MOTS_CLES + r"[A-Za-z0-9_\-]*"
    r"\s*[:=]\s*([^\s\"'#][^\s#]{11,})\s*$"
)

# Formats où une valeur s'écrit sans guillemets.
FORMATS_DE_CONFIGURATION = (".ini", ".cfg", ".conf", ".env", ".toml", ".properties")

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

# --------------------------------------------------------------------------
# Variables dont la valeur ne doit jamais etre un litteral
#
# Classe distincte, et non un motif de plus : ici le *nom* est le signal et la
# valeur ne l'est pas. Pour une cle de signature, n'importe quel litteral est
# fautif, quelle que soit son entropie.
#
# Un gabarit n'est donc pas un defaut moindre qu'une vraie cle : c'en est un
# autre, et souvent le pire des deux. Une cle fuitee finit par se reveler et
# se revoque ; une cle previsible signe des jetons valables sans laisser la
# moindre trace, et rien dans aucun journal ne la distingue d'une bonne cle.
#
# C'est pourquoi les filtres PLACEHOLDER et LOW_ENTROPY ne s'appliquent pas a
# cette classe. Ils ont raison sur leur terrain — « cle-secrete-temporaire »
# n'est pas un identifiant fuite — mais leur conclusion ne vaut que pour la
# question qu'ils posent. Celle-ci en est une autre.
# --------------------------------------------------------------------------

MUST_COME_FROM_ENV = re.compile(
    r"(?i)[A-Za-z0-9_\-]*"
    r"(?:secret[_\-]?key|signing[_\-]?key|jwt[_\-]?secret|session[_\-]?secret|"
    r"hmac[_\-]?key|encryption[_\-]?key|app[_\-]?secret|private[_\-]?key)"
    r"[A-Za-z0-9_\-]*\s*[:=]\s*[\"']([^\"']+)[\"']"
)

# Une valeur qui n'est pas un litteral mais un renvoi : interpolation de shell,
# de compose ou de gabarit. La lire, c'est lire l'environnement — donc
# exactement ce qui est demande. Seul ce filtre-la subsiste pour cette classe.
DEFERRED_VALUE = re.compile(r"^(?:\$\{[^}]*\}|\{\{[^}]*\}\}|\$[A-Za-z_][A-Za-z0-9_]*|<[^>]*>)$")

# Fichiers dont la raison d'etre est de montrer la forme d'une configuration.
# Une valeur factice y est le contenu attendu, pas un defaut.
SHAPE_ONLY_SUFFIXES = (".example", ".sample", ".template", ".dist")

# Répertoires écartés du parcours. Principe : **on n'écarte jamais un fichier
# que git suit.** Un contrôle dont l'objet est « aucun secret n'entre dans le
# dépôt » ne peut pas être aveugle à un fichier versionné, quel que soit le
# répertoire où il se range.
#
# `.dvc` figurait ici et a été retiré : `.dvc/config` **est versionné**, et
# `dvc remote modify` sans `--local` y écrit un mot de passe. Le seul cas que
# ce contrôle existe pour empêcher tombait donc dans son angle mort. Signalé
# par @DOUAEM449 (issue #71), qui avait relevé le répertoire ; la version
# versionnée du fichier est apparue en instruisant son constat.
DEFAULT_EXCLUDED_DIRS = frozenset(
    {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
)

# Sous-arbres écartés par leur chemin, et non par un composant de nom. Aucun
# n'est versionné : `.dvc/cache` et `.dvc/tmp` sont ignorés par
# `.dvc/.gitignore`, et ils contiennent des objets binaires en grand nombre.
EXCLUDED_PREFIXES = (
    ".dvc/cache",
    ".dvc/tmp",
)

# `.git/` reste écarté du parcours — des objets compressés par milliers, que
# lire n'apprendrait rien. Mais `.git/config` porte l'URL du remote, et une URL
# de remote se recopie : un `git remote -v` collé dans une conversation sort le
# jeton de la machine sans qu'aucun commit ait lieu. Le fichier est donc lu à
# part, hors du parcours.
#
# Ce n'est pas un secret « dans le dépôt » mais dans le clone local, et le
# rapport le dit : le correctif est `git remote set-url`, pas une suppression
# de fichier.
FICHIERS_HORS_PARCOURS = (".git/config",)

SCANNED_SUFFIXES = frozenset(
    {".py", ".js", ".mjs", ".ts", ".json", ".yml", ".yaml", ".html", ".css",
     ".md", ".txt", ".sh", ".cfg", ".ini", ".toml", ".env"}
)

# Fichiers de configuration sans extension. Second angle mort, independant du
# precedent : `.dvc/config` echappait au controle pour deux raisons cumulees —
# son repertoire etait exclu, *et* son nom n'a pas de suffixe. Lever une seule
# des deux n'aurait rien change, et l'aurait laisse croire corrige.
SCANNED_NAMES = frozenset({"config", "credentials", "Dockerfile", ".env"})

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
    chemin = Path(path)
    shape_only = chemin.suffix.lower() in SHAPE_ONLY_SUFFIXES
    # Un format de configuration : valeur nue attendue, guillemets facultatifs.
    config = (
        chemin.suffix.lower() in FORMATS_DE_CONFIGURATION
        or chemin.name in SCANNED_NAMES
    )
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if _is_allowed(lines, index):
            continue
        for kind, pattern in KNOWN_FORMS:
            for match in re.finditer(pattern, line):
                findings.append(
                    Finding(path, index + 1, kind, _redact(match.group(0)))
                )

        # Clé qui doit venir de l'environnement. Testée avant l'affectation
        # nommée, et sans les filtres de gabarit : c'est précisément le cas
        # qu'ils écartent à tort ici.
        if not shape_only:
            for match in MUST_COME_FROM_ENV.finditer(line):
                value = match.group(1).strip()
                if DEFERRED_VALUE.match(value):
                    continue
                findings.append(
                    Finding(
                        path,
                        index + 1,
                        "cle-a-charger-depuis-l-environnement",
                        _redact(value),
                    )
                )

        motifs_nommes = [NAMED_ASSIGNMENT]
        if config:
            motifs_nommes.append(NAMED_ASSIGNMENT_NU)
        for motif in motifs_nommes:
            for match in motif.finditer(line):
                value = match.group(1).strip()
                if PLACEHOLDER.match(value) or LOW_ENTROPY.match(value):
                    continue
                findings.append(
                    Finding(path, index + 1, "affectation-nommee", _redact(value))
                )

    # Une même ligne peut relever des deux classes ; ne la signaler qu'une
    # fois, sous le genre le plus précis, qui vient en premier.
    vus: set[tuple[int, str]] = set()
    uniques: list[Finding] = []
    for finding in findings:
        cle = (finding.line_no, finding.excerpt)
        if cle in vus:
            continue
        vus.add(cle)
        uniques.append(finding)
    return uniques


def iter_files(
    root: Path, excluded: Iterable[str] = DEFAULT_EXCLUDED_DIRS
) -> Iterator[Path]:
    excluded = set(excluded)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if (
            path.suffix.lower() not in SCANNED_SUFFIXES
            and path.name not in SCANNED_NAMES
        ):
            continue
        if any(part in excluded for part in path.parts):
            continue
        relatif = path.relative_to(root).as_posix()
        if relatif.startswith(EXCLUDED_PREFIXES):
            continue
        yield path


def iter_fichiers_hors_parcours(root: Path) -> Iterator[Path]:
    """Fichiers lus explicitement, bien que leur répertoire soit écarté.

    Aujourd'hui `.git/config` seul. Il n'entre pas dans le dépôt, mais il sort
    de la machine autrement : par un `git remote -v` recopié.
    """
    for relatif in FICHIERS_HORS_PARCOURS:
        chemin = root / relatif
        if chemin.is_file():
            yield chemin


def _lire(path: Path, root: Path) -> list[Finding]:
    try:
        texte = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return scan_text(texte, path.relative_to(root).as_posix())


def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        findings.extend(_lire(path, root))
    for path in iter_fichiers_hors_parcours(root):
        findings.extend(_lire(path, root))
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
