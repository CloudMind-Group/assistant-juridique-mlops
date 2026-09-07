"""M8 — contrôle des artefacts publiés.

Aucune sortie écrite dans ``data/processed/`` ne doit contenir de chemin brut
ni de nom de fichier source. Ce qui identifie un document dans un artefact
publié est son ``doc_id``.

**Pourquoi ce module existe.** La règle a déjà été enfreinte deux fois, par
deux personnes différentes, à six jours d'intervalle :

- ``ingestion_report.json`` enregistrait le chemin du fichier source
  (écart E-R13, corrigé par la PR #44) ;
- ``expectations_report.json`` a reproduit la même fuite (PR #52, corrigée
  par la PR #62), simplement parce qu'il n'existait pas quand la première
  correction a été écrite.

Le premier correctif substituait les chemins **à la sérialisation** du rapport
concerné. C'était juste pour ce fichier, et j'ai laissé cette portée se lire
comme une garantie générale. Elle ne l'était pas : elle protégeait un fichier,
pas la catégorie « artefact publié ».

Ce module traite la catégorie. Il ne corrige rien — il **constate**, sur les
fichiers réellement écrits, ce qu'aucune relecture de code ne peut garantir
pour un rapport qui n'existe pas encore.

Usage :
    python -m src.m8_compliance.artefacts_publies
    python -m src.m8_compliance.artefacts_publies --repertoire data/processed
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

# Extensions des fichiers sources. Leur présence dans un artefact publié
# signale un nom de fichier, donc potentiellement un nom de partie.
EXTENSIONS_SOURCE = (".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg")

# Forme produite par `ingest.diagnostic_ref` : <source_slug>-<16 hexa>.<ext>.
# Elle désigne un fichier sans le nommer, et reste sûre même quand le document
# n'a pas été ingéré — c'est le cas d'une erreur d'extraction.
REFERENCE_DIAGNOSTIC = re.compile(r"^[a-z_]+-[0-9a-f]{16}$")

# Chemin absolu, quelle que soit la plateforme. Il porte l'arborescence de la
# machine qui a produit l'artefact, donc souvent un nom d'utilisateur.
CHEMIN_ABSOLU = re.compile(r"(?:^[A-Za-z]:[/\\])|(?:^/(?:home|Users|root|var|mnt)/)")

# Chemin pointant dans le corpus brut, seul endroit où les noms de fichiers
# ont le droit d'exister.
CORPUS_BRUT = re.compile(r"data[/\\]raw[/\\]")

SUFFIXES_ANALYSES = (".json", ".jsonl")


@dataclass(frozen=True)
class Constat:
    fichier: str
    chemin_champ: str
    motif: str
    extrait: str

    def __str__(self) -> str:
        return f"{self.fichier} -> {self.chemin_champ}  [{self.motif}]  {self.extrait}"


def _tronquer(valeur: str, taille: int = 60) -> str:
    return valeur if len(valeur) <= taille else valeur[: taille - 1] + "..."


def _parcourir(valeur: Any, chemin: str = "") -> Iterator[tuple[str, str]]:
    """Produire chaque chaîne de la structure, avec le chemin qui y mène.

    Le chemin est conservé pour que le rapport désigne le champ fautif plutôt
    que le fichier entier : un rapport qui dit « quelque part dans ce fichier »
    fait perdre le temps de celui qui doit corriger.
    """
    if isinstance(valeur, str):
        yield chemin or "<racine>", valeur
    elif isinstance(valeur, dict):
        for cle, sous_valeur in valeur.items():
            yield from _parcourir(sous_valeur, f"{chemin}.{cle}" if chemin else str(cle))
    elif isinstance(valeur, (list, tuple)):
        for rang, element in enumerate(valeur):
            yield from _parcourir(element, f"{chemin}[{rang}]")


def analyser_valeur(
    chemin_champ: str, valeur: str, fichier: str, doc_ids: frozenset[str]
) -> list[Constat]:
    """Décider si une valeur nomme un fichier source.

    Le contrôle se calibre sur les `doc_id` réellement présents dans le corpus
    plutôt que sur une forme devinée. C'est nécessaire : `metadata.jsonl` porte
    un `file_path` vers `data/processed/<doc_id>.txt`, qui est une sortie
    dérivée de l'identifiant, pas le nom du fichier d'origine. Une règle qui se
    contenterait de l'extension signalerait ces cinquante chemins-là et ne
    servirait plus à rien — un contrôle bruyant finit désactivé.
    """
    constats: list[Constat] = []

    if CHEMIN_ABSOLU.search(valeur):
        constats.append(
            Constat(fichier, chemin_champ, "chemin absolu", _tronquer(valeur))
        )
    if CORPUS_BRUT.search(valeur):
        constats.append(
            Constat(fichier, chemin_champ, "chemin vers le corpus brut", _tronquer(valeur))
        )

    if not valeur.lower().endswith(EXTENSIONS_SOURCE):
        return constats

    nom = valeur.replace("\\", "/").rsplit("/", 1)[-1]
    souche = nom.rsplit(".", 1)[0]
    if not souche:
        # « .txt » seul est un format, pas un nom de fichier.
        return constats
    if souche in doc_ids or REFERENCE_DIAGNOSTIC.match(souche):
        return constats

    constats.append(
        Constat(fichier, chemin_champ, "nom de fichier source", _tronquer(valeur))
    )
    return constats


def _doc_ids_du_corpus(racine: Path) -> frozenset[str]:
    """Lire les `doc_id` écrits par le pipeline, pour calibrer le contrôle.

    Un nom de fichier dont la souche est un `doc_id` connu ne nomme personne :
    il désigne une sortie. Tout autre nom porté par un artefact publié est un
    nom choisi par qui a collecté le document — donc potentiellement celui
    d'une partie.
    """
    index = racine / "metadata.jsonl"
    if not index.exists():
        return frozenset()
    identifiants: set[str] = set()
    for ligne in index.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            fiche = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if isinstance(fiche, dict) and isinstance(fiche.get("doc_id"), str):
            identifiants.add(fiche["doc_id"])
    return frozenset(identifiants)


def analyser_fichier(
    fichier: Path, racine: Path, doc_ids: frozenset[str] = frozenset()
) -> list[Constat]:
    nom = str(fichier.relative_to(racine)).replace("\\", "/")
    constats: list[Constat] = []
    try:
        texte = fichier.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return constats

    lignes = texte.splitlines() if fichier.suffix == ".jsonl" else [texte]
    for rang, ligne in enumerate(lignes, start=1):
        if not ligne.strip():
            continue
        try:
            charge = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        prefixe = f"L{rang}." if fichier.suffix == ".jsonl" else ""
        for chemin_champ, valeur in _parcourir(charge):
            constats.extend(
                analyser_valeur(prefixe + chemin_champ, valeur, nom, doc_ids)
            )
    return constats


def verifier(racine: Path) -> list[Constat]:
    constats: list[Constat] = []
    if not racine.exists():
        return constats
    doc_ids = _doc_ids_du_corpus(racine)
    for fichier in sorted(racine.rglob("*")):
        if fichier.is_file() and fichier.suffix.lower() in SUFFIXES_ANALYSES:
            constats.extend(analyser_fichier(fichier, racine, doc_ids))
    return constats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie qu'aucun artefact publié ne nomme un fichier source"
    )
    parser.add_argument("--repertoire", default="data/processed")
    args = parser.parse_args()

    racine = Path(args.repertoire)
    if not racine.exists():
        print(f"{racine} absent : rien à vérifier")
        return 0

    constats = verifier(racine)
    if not constats:
        print(f"aucun chemin brut ni nom de fichier source dans {racine}")
        return 0

    print(f"{len(constats)} occurrence(s) dans les artefacts publiés :\n")
    for constat in constats:
        print(f"  {constat}")
    print(
        "\nUn artefact de `data/processed/` est poussé sur le remote partagé. "
        "Ce qui identifie un document y est son `doc_id`, jamais son nom de "
        "fichier — voir l'écart E-R13 du registre RGPD."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
