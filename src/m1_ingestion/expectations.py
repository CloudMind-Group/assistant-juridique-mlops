"""
Module 1 — Contrôle qualité déclaratif avec Great Expectations.

Le cahier des charges (carte 02) demande explicitement Great Expectations
exécuté dans la CI, « un jeu non conforme bloque la chaîne ». C'est ce que
fait ce module : il charge ``metadata.jsonl``, lui applique une suite
d'attentes déclarées, écrit un rapport, et sort en code 1 si une attente
échoue.

Pourquoi en plus de ``quality.py`` — les deux ne font pas le même travail :

  - ``quality.py`` valide **chaque document** un par un (le fichier texte
    existe-t-il, est-il vide, le schéma Pydantic passe-t-il). Il répond à
    « ce document est-il exploitable ? ».
  - Ce module valide **le jeu de données comme un tout** (les doc_id sont
    ils uniques entre eux, la table a-t-elle exactement les colonnes du
    contrat, le corpus est-il vide). Il répond à « ce jeu est-il livrable
    à M2 ? ».

Un doublon d'identifiant passe le premier contrôle et échoue le second :
chaque document est valide isolément, l'ensemble ne l'est pas.

Usage :
    python -m src.m1_ingestion.expectations
    python -m src.m1_ingestion.expectations --processed-dir data/processed \
        --fail-on-error
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from src.m1_ingestion.metadata_schema import Language, SourceType
from src.m1_ingestion.metadata_schema import DocumentMetadata

logger = logging.getLogger("m1_ingestion.expectations")

SUITE_NAME = "m1_corpus_juridique"

# Le contrat de colonnes est dérivé du schéma Pydantic, pas recopié : une
# liste recopiée diverge du schéma sans que personne ne le voie, et c'est
# exactement le genre d'écart que ce module est censé attraper.
EXPECTED_COLUMNS = sorted(DocumentMetadata.model_fields)

# Colonnes qui ne doivent JAMAIS apparaître dans l'index de métadonnées.
# Ce ne sont pas des hypothèses : ce dépôt a déjà écrit deux fois un chemin
# ou un nom de fichier brut dans une sortie publiée (champ
# `original_filename`, puis le chemin source dans ingestion_report.json).
# Le nom d'un fichier de jurisprudence porte régulièrement le nom d'une
# partie. L'attente `ExpectTableColumnsToMatchSet(exact_match=True)`
# ci-dessous les rejette toutes, connues comme inconnues ; cette liste
# existe pour documenter le motif et pour être testée explicitement.
COLONNES_INTERDITES = (
    "original_filename",
    "source_path",
    "raw_path",
    "absolute_path",
    "author",
    "email",
)

# Bornes de vraisemblance d'un document juridique. Volontairement larges :
# leur rôle est d'attraper un pipeline cassé (extraction vide, boucle qui
# duplique un texte), pas de juger de la qualité rédactionnelle.
MIN_MOTS_PAR_DOCUMENT = 5  # aligné sur quality.MIN_TOKENS
MAX_MOTS_PAR_DOCUMENT = 20_000  # aligné sur quality.MAX_TOKENS

_DATE_REGEX = r"^\d{4}(?:-\d{2}-\d{2})?$"
# doc_id sans espace : c'est la règle du schéma (doc_id_no_whitespace), on la
# réexprime ici pour qu'elle soit vérifiée sur le jeu livré, pas seulement à
# la construction.
_DOC_ID_REGEX = r"^\S+$"
# Un chemin absolu (« /var/... » ou « C:\... ») dans le jeu livré signifie
# qu'une arborescence locale a fuité hors de la machine qui a ingéré.
_CHEMIN_RELATIF_REGEX = r"^(?![A-Za-z]:[\\/])(?![\\/]).+"


def charger_metadonnees(metadata_path: Path) -> pd.DataFrame:
    """Charge metadata.jsonl en DataFrame, en échouant sur une ligne illisible."""
    if not metadata_path.exists():
        raise FileNotFoundError(f"Index de métadonnées introuvable : {metadata_path}")

    lignes: list[dict[str, Any]] = []
    with metadata_path.open(encoding="utf-8") as f:
        for numero, ligne in enumerate(f, start=1):
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                lignes.append(json.loads(ligne))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSON invalide ligne {numero} de {metadata_path} : {exc}"
                ) from exc

    return pd.DataFrame(lignes)


def construire_suite() -> gx.ExpectationSuite:
    """La suite d'attentes : le contrat du jeu de données, en déclaratif.

    Chaque attente correspond à une façon dont le corpus a déjà cassé ou
    pourrait casser silencieusement. Une attente qu'on ne saurait pas
    justifier n'a rien à faire ici.
    """
    suite = gx.ExpectationSuite(name=SUITE_NAME)

    # --- Structure de la table -----------------------------------------
    # Un corpus vide passe tous les contrôles par document (il n'y en a
    # aucun à contrôler) et serait livré à M2 sans un bruit.
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1))
    # exact_match : toute colonne en trop est rejetée, y compris celles de
    # COLONNES_INTERDITES. C'est le garde-fou contre la réapparition d'un
    # champ qui porterait des données personnelles.
    suite.add_expectation(
        gxe.ExpectTableColumnsToMatchSet(
            column_set=EXPECTED_COLUMNS, exact_match=True
        )
    )

    # --- Identité des documents ----------------------------------------
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="doc_id"))
    # L'unicité est LA vérification que quality.py ne peut pas faire : elle
    # ne se voit qu'à l'échelle du jeu. Deux documents de même doc_id, et M2
    # en indexe un seul sans erreur.
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="doc_id"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToMatchRegex(column="doc_id", regex=_DOC_ID_REGEX)
    )

    # --- Métadonnées obligatoires ---------------------------------------
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(column="title", min_value=1)
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="source", value_set=[s.value for s in SourceType]
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(
            column="language", value_set=[langue.value for langue in Language]
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToMatchRegex(column="date", regex=_DATE_REGEX)
    )
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="category"))

    # --- Chemins ---------------------------------------------------------
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="file_path"))
    suite.add_expectation(
        gxe.ExpectColumnValuesToMatchRegex(
            column="file_path", regex=_CHEMIN_RELATIF_REGEX
        )
    )

    # --- Volumétrie ------------------------------------------------------
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(
            column="word_count_clean",
            min_value=MIN_MOTS_PAR_DOCUMENT,
            max_value=MAX_MOTS_PAR_DOCUMENT,
        )
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(column="char_count_clean", min_value=1)
    )
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeBetween(column="segment_count", min_value=0)
    )

    # --- État du traitement ----------------------------------------------
    # Seuls les documents traités avec succès ont le droit d'entrer dans
    # l'index : un document en échec qui y figure est un bug de pipeline,
    # pas un document de mauvaise qualité.
    suite.add_expectation(
        gxe.ExpectColumnValuesToBeInSet(column="status", value_set=["SUCCESS"])
    )

    return suite


def valider(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Exécute la suite sur le DataFrame et renvoie le résultat brut GE."""
    contexte = gx.get_context(mode="ephemeral")
    source = contexte.data_sources.add_pandas("m1_corpus")
    actif = source.add_dataframe_asset(name="metadata")
    lot = actif.add_batch_definition_whole_dataframe("jeu_complet")

    suite = contexte.suites.add(construire_suite())
    definition = contexte.validation_definitions.add(
        gx.ValidationDefinition(data=lot, suite=suite, name="validation_m1")
    )

    resultat = definition.run(batch_parameters={"dataframe": dataframe})
    return resultat.to_json_dict()


def _resumer(resultat: dict[str, Any]) -> dict[str, Any]:
    """Réduit le résultat GE à ce qu'un humain lit dans un log de CI.

    Le rapport GE complet fait plusieurs milliers de lignes ; personne ne
    le lit dans une sortie d'Actions. On garde le verdict, le décompte, et
    la liste des attentes en échec avec ce qui a été observé.
    """
    resultats = resultat.get("results", [])
    echecs = []
    for r in resultats:
        if r.get("success"):
            continue
        config = r.get("expectation_config", {})
        kwargs = config.get("kwargs", {})
        resultat_detail = r.get("result", {})
        echecs.append(
            {
                "attente": config.get("type", "inconnue"),
                "colonne": kwargs.get("column"),
                "elements_en_echec": resultat_detail.get("unexpected_count"),
                "exemples": resultat_detail.get("partial_unexpected_list", [])[:5],
            }
        )

    statistiques = resultat.get("statistics", {})
    return {
        "succes": bool(resultat.get("success")),
        "attentes_evaluees": statistiques.get("evaluated_expectations", len(resultats)),
        "attentes_reussies": statistiques.get("successful_expectations", 0),
        "attentes_en_echec": statistiques.get("unsuccessful_expectations", len(echecs)),
        "echecs": echecs,
    }


def executer(processed_dir: Path) -> dict[str, Any]:
    dataframe = charger_metadonnees(processed_dir / "metadata.jsonl")
    logger.info(
        "Corpus chargé : %d documents, %d colonnes", len(dataframe), len(dataframe.columns)
    )

    brut = valider(dataframe)
    resume = _resumer(brut)

    rapport = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "processed_dir": processed_dir.as_posix(),
        "suite": SUITE_NAME,
        "documents": len(dataframe),
        **resume,
    }

    if resume["succes"]:
        logger.info(
            "Great Expectations : %d/%d attentes satisfaites",
            resume["attentes_reussies"],
            resume["attentes_evaluees"],
        )
    else:
        for echec in resume["echecs"]:
            logger.error(
                "Attente en échec : %s sur '%s' — %s élément(s) non conforme(s), ex. %s",
                echec["attente"],
                echec["colonne"],
                echec["elements_en_echec"],
                echec["exemples"],
            )

    return rapport


def ecrire_rapport(rapport: dict[str, Any], processed_dir: Path) -> Path:
    chemin = processed_dir / "expectations_report.json"
    chemin.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    logger.info("Rapport écrit : %s", chemin)
    return chemin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M1 — contrôle qualité du jeu de données (Great Expectations)"
    )
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Sort en code 1 si une attente échoue (CI / DVC / Airflow).",
    )
    return parser.parse_args()


def main() -> dict[str, Any]:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    rapport = executer(args.processed_dir)
    ecrire_rapport(rapport, args.processed_dir)

    if args.fail_on_error and not rapport["succes"]:
        raise SystemExit(1)
    return rapport


if __name__ == "__main__":
    main()
