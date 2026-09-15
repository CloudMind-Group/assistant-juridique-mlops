"""
Module 1 — Génération automatique de la Data Card du corpus.

Une Data Card documente un jeu de données comme une fiche produit : ce qu'il
contient, d'où il vient, ce qu'on lui a fait subir, ce pour quoi il est
utilisable — et surtout ce pour quoi il ne l'est pas. Elle est générée à
partir des sorties réelles du pipeline (``metadata.jsonl``,
``segments.jsonl``, ``ingestion_report.json``, ``quality_report.json``),
jamais saisie à la main, pour qu'elle ne puisse pas mentir sur l'état du
corpus : si le chiffre change, la carte change au prochain ``dvc repro``.

Deux sorties, même contenu :
  - ``data/processed/data_card.json`` — lisible par machine (CI, M8, audit) ;
  - ``data/processed/DATA_CARD.md``   — lisible par un humain (revue, rapport).

Les sections qualitatives (usages prévus, hors-périmètre, limites connues)
sont des constantes de ce module et non des chiffres calculés : elles
engagent l'équipe et doivent passer en revue de code pour changer.

Usage :
    python -m src.m1_ingestion.data_card
    python -m src.m1_ingestion.data_card --processed-dir data/processed \
        --corpus-status synthetique
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence

from src.m1_ingestion.anonymization_schema import DEFAULT_RULE_SET
from src.m1_ingestion.ingest import FOLDER_TO_SOURCE

logger = logging.getLogger("m1_ingestion.data_card")

CORPUS_NAME = "Corpus juridique marocain — assistant-juridique-mlops (Module 1)"
CORPUS_OWNER = "Module M1 — Data Pipeline & Preprocessing"

# --- Statuts de corpus -------------------------------------------------
# Le pipeline ne peut PAS déduire seul si les documents qu'il traite sont
# réels ou fabriqués : rien dans metadata.jsonl ne le dit. Le statut est
# donc un paramètre explicite, dont la valeur par défaut est le cas le plus
# prudent. Le jour où de vrais documents entrent dans data/raw, quelqu'un
# doit changer ce drapeau dans dvc.yaml — un geste délibéré, visible en
# revue, plutôt qu'une carte qui se met à mentir en silence.
CORPUS_STATUS_CHOICES = ("synthetique", "reel", "mixte")

CORPUS_STATUS_LABELS = {
    "synthetique": (
        "**100 % synthétique.** Les documents sont fabriqués par "
        "`src/m1_ingestion/dataset_generator.py` pour faire tourner le "
        "pipeline de bout en bout sans attendre la collecte réelle. Aucun "
        "texte de ce corpus n'a de valeur juridique et aucun ne doit être "
        "cité comme source de droit."
    ),
    "reel": (
        "**Documents réels.** Le corpus provient de sources juridiques "
        "authentiques. La conformité (droits de réutilisation, CGU des "
        "portails sources, données personnelles) doit avoir été vérifiée "
        "en amont de l'ingestion."
    ),
    "mixte": (
        "**Mixte.** Le corpus contient à la fois des documents réels et des "
        "documents synthétiques, sans distinction portée par les métadonnées. "
        "Ne pas s'appuyer sur ce corpus pour une évaluation qui suppose des "
        "textes authentiques tant que les deux populations ne sont pas "
        "étiquetées séparément."
    ),
}

USAGES_PREVUS = (
    "Alimenter l'indexation et la recherche sémantique du module M2 (RAG).",
    "Servir de base d'évaluation hors ligne aux modules M3 (expérimentation) "
    "et M6 (évaluation de la génération).",
    "Fournir un jeu de référence stable et versionné par DVC pour les tests "
    "de non-régression du pipeline.",
)

HORS_PERIMETRE = (
    "Fournir un conseil juridique. Le corpus alimente un assistant de "
    "recherche documentaire, pas un avocat.",
    "Servir de source faisant foi. Le texte officiel reste le Bulletin "
    "Officiel publié.",
    "Entraîner un modèle destiné à décider d'une situation individuelle "
    "(embauche, litige, sanction) sans supervision humaine.",
)

LIMITES_CONNUES = (
    "L'anonymisation repose sur des règles regex, pas sur un modèle de NER. "
    "Elle rattrape les formes attendues (CIN, téléphone, e-mail, nom précédé "
    "d'un marqueur de rôle) et laissera passer les formulations qu'aucune "
    "règle ne couvre. Un rappel de 100 % n'est ni mesuré ni promis.",
    "La segmentation en articles et alinéas s'appuie sur des marqueurs "
    "typographiques. Un document mal structuré, mal océrisé ou sans "
    "numérotation ressort en un seul segment.",
    "Les documents issus d'OCR portent le bruit de l'OCR. Le champ "
    "`extraction_method` permet de les isoler ; il n'existe pas de mesure "
    "du taux d'erreur caractère.",
    "La déduplication est exacte (SHA-256 du texte nettoyé) : deux versions "
    "d'un même arrêt différant d'un espace comptent pour deux documents.",
    "La couverture par source, par langue et par période est celle des "
    "tableaux ci-dessous — elle n'a pas été construite pour être "
    "représentative d'une population de référence.",
)

MAINTENANCE = (
    "Régénérée automatiquement à chaque `dvc repro` de l'étape `data_card`.",
    "Provenance et versions des données assurées par DVC (`dvc.lock`), "
    "remote sur DAGsHub.",
    "Toute évolution du schéma de métadonnées se fait par ajout de champs "
    "optionnels (voir `metadata_schema.py`) afin de ne pas casser M2.",
)


# --- Chargement ---------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Charge un .jsonl en échouant fort sur une ligne corrompue.

    Même choix que dans quality.py : une ligne illisible est une anomalie
    de pipeline, pas un incident à journaliser puis oublier. Une Data Card
    calculée sur un fichier tronqué serait fausse sans le dire.
    """
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSON invalide ligne {line_no} de {path} : {exc}"
                ) from exc
    return records


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# --- Agrégations --------------------------------------------------------


def _counts(values: Sequence[Any], *, unknown: str = "(non renseigné)") -> dict[str, int]:
    """Compte trié par clé — l'ordre doit être stable d'un run à l'autre,
    sinon DVC voit une sortie modifiée à chaque exécution."""
    counter = Counter(str(v) if v not in (None, "") else unknown for v in values)
    return dict(sorted(counter.items()))


def _distribution(values: Sequence[float]) -> dict[str, float]:
    """Distribution résumée. La médiane figure à côté de la moyenne parce
    qu'un seul document très long suffit à rendre la moyenne trompeuse."""
    if not values:
        return {"n": 0, "min": 0, "median": 0, "mean": 0, "max": 0, "total": 0}
    return {
        "n": len(values),
        "min": min(values),
        "median": round(median(values), 2),
        "mean": round(mean(values), 2),
        "max": max(values),
        "total": sum(values),
    }


def summarize_composition(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Ce qu'il y a dans le corpus, vu depuis metadata.jsonl."""
    years = [str(r.get("date", ""))[:4] for r in records if r.get("date")]
    sources_presentes = {str(r.get("source")) for r in records}
    sources_connues = {s.value for s in FOLDER_TO_SOURCE.values()}

    return {
        "documents": len(records),
        "par_source": _counts([r.get("source") for r in records]),
        "par_langue": _counts([r.get("language") for r in records]),
        "par_categorie": _counts([r.get("category") for r in records]),
        "par_format_source": _counts([r.get("source_format") for r in records]),
        "par_methode_extraction": _counts([r.get("extraction_method") for r in records]),
        "par_annee": _counts(years),
        # Une source déclarée dans FOLDER_TO_SOURCE mais absente du corpus
        # est un trou de couverture, pas un détail : c'est exactement ce qui
        # distingue « le connecteur existe » de « le connecteur a collecté ».
        "sources_declarees_sans_document": sorted(sources_connues - sources_presentes),
        "caracteres_nettoyes": _distribution(
            [int(r.get("char_count_clean", 0)) for r in records]
        ),
        "mots_nettoyes": _distribution(
            [int(r.get("word_count_clean", 0)) for r in records]
        ),
    }


def summarize_segments(
    segments: Sequence[dict[str, Any]], records: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Découpage en articles/alinéas — la matière première de M2."""
    per_doc = Counter(str(s.get("doc_id")) for s in segments)
    doc_ids = [str(r.get("doc_id")) for r in records]
    # Un document sans segment n'apparaît pas dans segments.jsonl : il faut
    # le compter depuis metadata.jsonl, sinon il disparaît du bilan.
    counts_par_doc = [per_doc.get(doc_id, 0) for doc_id in doc_ids]

    return {
        "segments": len(segments),
        "par_type": _counts([s.get("kind") for s in segments]),
        "segments_par_document": _distribution(counts_par_doc),
        "documents_sans_segment": sum(1 for c in counts_par_doc if c == 0),
        "caracteres_par_segment": _distribution(
            [len(str(s.get("text", ""))) for s in segments]
        ),
    }


def summarize_quality(quality_report: dict[str, Any]) -> dict[str, Any]:
    """Résultat des contrôles qualité, erreurs regroupées par message."""
    results = quality_report.get("results", [])
    erreurs = Counter(e for r in results for e in r.get("errors", []))
    avertissements = Counter(w for r in results for w in r.get("warnings", []))

    return {
        "documents_controles": quality_report.get("total_documents", 0),
        "reussis": quality_report.get("passed", 0),
        "echoues": quality_report.get("failed", 0),
        "taux_reussite": quality_report.get("pass_rate", 0.0),
        "documents_en_echec": sorted(
            str(r.get("doc_id")) for r in results if not r.get("passed", False)
        ),
        "erreurs_frequentes": dict(erreurs.most_common(10)),
        "avertissements_frequents": dict(avertissements.most_common(10)),
    }


def summarize_privacy(
    records: Sequence[dict[str, Any]], ingestion_report: dict[str, Any]
) -> dict[str, Any]:
    """Ce que l'anonymisation a fait, et ce qu'elle ne garantit pas."""
    types_couverts = sorted({str(rule.pii_type) for rule in DEFAULT_RULE_SET.rules})
    return {
        "documents_anonymises": sum(1 for r in records if r.get("anonymized")),
        "occurrences_masquees": ingestion_report.get("pii_masked", 0),
        "regles_actives": len(DEFAULT_RULE_SET.rules),
        "types_pii_couverts": types_couverts,
        "methode": "règles regex (voir anonymization_schema.py), pas de NER",
        "garantie_de_rappel": None,
    }


def summarize_ingestion(ingestion_report: dict[str, Any]) -> dict[str, Any]:
    """Reprise des compteurs du pipeline d'ingestion, sans recalcul."""
    return {
        "fichiers_decouverts": ingestion_report.get("total_files_discovered", 0),
        "traites": ingestion_report.get("processed", 0),
        "ignores": ingestion_report.get("skipped", 0),
        "en_echec": ingestion_report.get("failed", 0),
        "taux_succes": ingestion_report.get("success_rate", 0.0),
        "doublons_ecartes": ingestion_report.get("duplicates", 0),
        "erreurs": ingestion_report.get("errors", []),
    }


# --- Carte --------------------------------------------------------------


@dataclass
class DataCard:
    generated_at: str
    nom: str
    proprietaire: str
    statut_corpus: str
    processed_dir: str
    ingestion: dict[str, Any]
    composition: dict[str, Any]
    segmentation: dict[str, Any]
    qualite: dict[str, Any]
    confidentialite: dict[str, Any]
    usages_prevus: tuple[str, ...]
    hors_perimetre: tuple[str, ...]
    limites_connues: tuple[str, ...]
    maintenance: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "nom": self.nom,
            "proprietaire": self.proprietaire,
            "statut_corpus": self.statut_corpus,
            "processed_dir": self.processed_dir,
            "ingestion": self.ingestion,
            "composition": self.composition,
            "segmentation": self.segmentation,
            "qualite": self.qualite,
            "confidentialite": self.confidentialite,
            "usages_prevus": list(self.usages_prevus),
            "hors_perimetre": list(self.hors_perimetre),
            "limites_connues": list(self.limites_connues),
            "maintenance": list(self.maintenance),
        }


def build_data_card(
    processed_dir: Path, *, corpus_status: str = "synthetique"
) -> DataCard:
    if corpus_status not in CORPUS_STATUS_CHOICES:
        raise ValueError(
            f"statut de corpus inconnu : {corpus_status!r} "
            f"(attendu : {', '.join(CORPUS_STATUS_CHOICES)})"
        )

    records = _load_jsonl(processed_dir / "metadata.jsonl")
    segments = _load_jsonl(processed_dir / "segments.jsonl")
    ingestion_report = _load_json(processed_dir / "ingestion_report.json")
    quality_report = _load_json(processed_dir / "quality_report.json")

    card = DataCard(
        generated_at=datetime.now(timezone.utc).isoformat(),
        nom=CORPUS_NAME,
        proprietaire=CORPUS_OWNER,
        statut_corpus=corpus_status,
        processed_dir=processed_dir.as_posix(),
        ingestion=summarize_ingestion(ingestion_report),
        composition=summarize_composition(records),
        segmentation=summarize_segments(segments, records),
        qualite=summarize_quality(quality_report),
        confidentialite=summarize_privacy(records, ingestion_report),
        usages_prevus=USAGES_PREVUS,
        hors_perimetre=HORS_PERIMETRE,
        limites_connues=LIMITES_CONNUES,
        maintenance=MAINTENANCE,
    )
    logger.info(
        "Data Card construite : %d documents, %d segments, statut=%s",
        card.composition["documents"],
        card.segmentation["segments"],
        corpus_status,
    )
    return card


# --- Rendu Markdown -----------------------------------------------------


def _table(titre_cle: str, titre_valeur: str, mapping: dict[str, int]) -> str:
    if not mapping:
        return "_Aucune donnée._\n"
    total = sum(mapping.values()) or 1
    lignes = [f"| {titre_cle} | {titre_valeur} | % |", "| --- | ---: | ---: |"]
    for cle, valeur in mapping.items():
        lignes.append(f"| {cle} | {valeur} | {valeur / total * 100:.1f} % |")
    return "\n".join(lignes) + "\n"


def _dist_table(titre: str, dist: dict[str, float]) -> str:
    return (
        f"| {titre} | n | min | médiane | moyenne | max | total |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
        f"| valeurs | {dist['n']} | {dist['min']} | {dist['median']} | "
        f"{dist['mean']} | {dist['max']} | {dist['total']} |\n"
    )


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items) + "\n"


def render_markdown(card: DataCard) -> str:
    c, s, q, p, i = (
        card.composition,
        card.segmentation,
        card.qualite,
        card.confidentialite,
        card.ingestion,
    )

    absentes = c["sources_declarees_sans_document"]
    bloc_absentes = (
        "\n> **Trou de couverture.** Aucune donnée pour : "
        + ", ".join(absentes)
        + ". Ces sources sont déclarées dans le pipeline mais rien n'a encore "
        "été collecté pour elles.\n"
        if absentes
        else ""
    )

    echecs = q["documents_en_echec"]
    bloc_echecs = (
        "\nDocuments en échec : " + ", ".join(f"`{d}`" for d in echecs) + "\n"
        if echecs
        else "\nAucun document en échec.\n"
    )

    # Les tableaux d'erreurs et d'avertissements ne s'affichent que s'il y a
    # quelque chose à montrer : un « _Aucune donnée._ » sous un titre absent
    # ne renseigne personne.
    bloc_erreurs = (
        "\n### Erreurs les plus fréquentes\n\n"
        + _table("Erreur", "Occurrences", q["erreurs_frequentes"])
        if q["erreurs_frequentes"]
        else ""
    )
    bloc_avertissements = (
        "\n### Avertissements les plus fréquents\n\n"
        + _table("Avertissement", "Occurrences", q["avertissements_frequents"])
        if q["avertissements_frequents"]
        else ""
    )

    sans_segment = s["documents_sans_segment"]
    part_sans_segment = (
        f" ({sans_segment / c['documents'] * 100:.1f} % du corpus)"
        if c["documents"]
        else ""
    )

    return f"""# Data Card — {card.nom}

> Fichier **généré automatiquement** par `src/m1_ingestion/data_card.py`
> (étape DVC `data_card`). Ne pas éditer à la main : toute modification sera
> écrasée au prochain `dvc repro`. Pour changer les sections qualitatives,
> modifier les constantes du module et passer en revue de code.

- **Propriétaire :** {card.proprietaire}
- **Généré le :** {card.generated_at}
- **Répertoire décrit :** `{card.processed_dir}`

## 1. Nature du corpus

{CORPUS_STATUS_LABELS[card.statut_corpus]}

## 2. Ingestion

| Indicateur | Valeur |
| --- | ---: |
| Fichiers découverts | {i['fichiers_decouverts']} |
| Traités | {i['traites']} |
| Ignorés | {i['ignores']} |
| En échec | {i['en_echec']} |
| Taux de succès | {i['taux_succes'] * 100:.1f} % |
| Doublons écartés (SHA-256) | {i['doublons_ecartes']} |

## 3. Composition

**{c['documents']} documents.**
{bloc_absentes}
### Par source

{_table("Source", "Documents", c['par_source'])}
### Par langue

{_table("Langue", "Documents", c['par_langue'])}
### Par catégorie

{_table("Catégorie", "Documents", c['par_categorie'])}
### Par format d'origine

{_table("Format", "Documents", c['par_format_source'])}
### Par méthode d'extraction

{_table("Méthode", "Documents", c['par_methode_extraction'])}
### Par année

{_table("Année", "Documents", c['par_annee'])}
### Volume textuel (après nettoyage et anonymisation)

{_dist_table("Caractères / document", c['caracteres_nettoyes'])}
{_dist_table("Mots / document", c['mots_nettoyes'])}
## 4. Segmentation

**{s['segments']} segments** (articles et alinéas) issus de {c['documents']} documents.

{_table("Type de segment", "Segments", s['par_type'])}
{_dist_table("Segments / document", s['segments_par_document'])}
{_dist_table("Caractères / segment", s['caracteres_par_segment'])}
Documents sans aucun segment détecté : **{sans_segment}**{part_sans_segment}.
Ces documents restent indexables tels quels par M2, mais sans découpage
article par article — leur granularité de recherche est celle du document
entier.

## 5. Qualité

| Indicateur | Valeur |
| --- | ---: |
| Documents contrôlés | {q['documents_controles']} |
| Réussis | {q['reussis']} |
| Échoués | {q['echoues']} |
| Taux de réussite | {q['taux_reussite'] * 100:.1f} % |
{bloc_echecs}{bloc_erreurs}{bloc_avertissements}
## 6. Données personnelles

| Indicateur | Valeur |
| --- | ---: |
| Documents anonymisés | {p['documents_anonymises']} |
| Occurrences masquées | {p['occurrences_masquees']} |
| Règles actives | {p['regles_actives']} |

Types de PII couverts : {', '.join(f"`{t}`" for t in p['types_pii_couverts'])}.

Méthode : {p['methode']}.

> **Aucun taux de rappel n'est garanti.** Le détecteur repose sur des motifs
> explicites : il ne voit que ce qu'une règle décrit. Le banc d'évaluation PII
> de M8 mesure sa performance par langue et par famille — s'y référer avant
> de traiter ce corpus comme dépourvu de données personnelles.

## 7. Usages prévus

{_bullets(card.usages_prevus)}
## 8. Hors périmètre

{_bullets(card.hors_perimetre)}
## 9. Limites connues

{_bullets(card.limites_connues)}
## 10. Maintenance et provenance

{_bullets(card.maintenance)}"""


# --- Écriture et CLI ----------------------------------------------------


def write_card(card: DataCard, processed_dir: Path) -> tuple[Path, Path]:
    json_path = processed_dir / "data_card.json"
    md_path = processed_dir / "DATA_CARD.md"

    json_path.write_text(
        json.dumps(card.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(render_markdown(card), encoding="utf-8")

    logger.info("Data Card écrite : %s et %s", json_path, md_path)
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1 — génération de la Data Card")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--corpus-status",
        choices=CORPUS_STATUS_CHOICES,
        default="synthetique",
        help=(
            "Nature des documents ingérés. Le pipeline ne peut pas la deviner : "
            "à changer explicitement le jour où de vrais documents entrent."
        ),
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> DataCard:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    card = build_data_card(args.processed_dir, corpus_status=args.corpus_status)
    write_card(card, args.processed_dir)
    return card


if __name__ == "__main__":
    main()
