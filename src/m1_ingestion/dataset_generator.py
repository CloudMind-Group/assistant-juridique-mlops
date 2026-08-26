"""
Synthetic sample corpus generator for Module 1.

Generates 50-100 realistic (but fabricated) Moroccan legal documents across
the 3 M1 sources — Bulletin Officiel, Jurisprudence, Contrats Types — in
French and Arabic, so Module 2 (Imane) can start indexing immediately
without waiting on real corpus collection. Output is written to
``data/raw/<source_slug>/`` (gitignored) as ``.txt`` + ``.meta.json``
sidecars consumable by :mod:`src.m1_ingestion.ingest`.

This is synthetic placeholder content for pipeline testing — NOT to be
treated as authoritative legal text.

Usage:
    python -m src.m1_ingestion.dataset_generator --count 60
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger("m1_ingestion.dataset_generator")

RAW_DIR = Path("data/raw")

BO_CATEGORIES_FR = [
    "Droit du travail",
    "Droit des affaires",
    "Droit civil",
    "Droit fiscal",
    "Droit social",
]

JURISPRUDENCE_JURIDICTIONS = [
    "Cour de Cassation",
    "Cour d'Appel de Rabat",
    "Cour d'Appel de Casablanca",
    "Tribunal de Première Instance de Fès",
]

CONTRAT_TYPES = [
    "Contrat de travail à durée indéterminée",
    "Contrat de travail à durée déterminée",
    "Contrat de bail à usage d'habitation",
    "Contrat de vente immobilière",
    "Contrat de prestation de services",
]

BO_ARTICLE_BODY_FR = (
    "Conformément aux dispositions de la loi n° 65-99 relative au Code du "
    "Travail, l'employeur est tenu de garantir au salarié des conditions de "
    "travail conformes à la dignité humaine et à la réglementation en "
    "vigueur. Tout manquement à cette obligation expose l'employeur aux "
    "sanctions prévues par le présent Dahir."
)

BO_ARTICLE_BODY_AR = (
    "طبقا لأحكام القانون رقم 65.99 المتعلق بمدونة الشغل، يلتزم المشغل بضمان "
    "ظروف عمل تليق بالكرامة الإنسانية ومطابقة للتنظيم الجاري به العمل. كل "
    "إخلال بهذا الالتزام يعرض المشغل للعقوبات المنصوص عليها في هذا الظهير."
)

JURISPRUDENCE_BODY_FR = (
    "Attendu que la partie demanderesse invoque la rupture abusive du "
    "contrat de travail ; Attendu que les pièces versées au dossier "
    "établissent l'absence de procédure disciplinaire régulière ; Par ces "
    "motifs, la Cour déclare le licenciement abusif et condamne l'employeur "
    "au versement des indemnités légales."
)

JURISPRUDENCE_BODY_AR = (
    "حيث تمسك الطالب بالفصل التعسفي من العمل، وحيث إن الوثائق المدلى بها "
    "تثبت غياب مسطرة تأديبية قانونية، فإنه لهذه الأسباب تصرح المحكمة بأن "
    "الفصل تعسفي وتحكم على المشغل بأداء التعويضات القانونية."
)

CONTRAT_BODY_FR = (
    "Entre les soussignés, d'une part {partie_a}, et d'autre part "
    "{partie_b}, il a été convenu et arrêté ce qui suit : Article 1 - Objet "
    "du contrat. Article 2 - Obligations des parties. Article 3 - Durée et "
    "résiliation. Article 4 - Litiges : tout différend relatif à "
    "l'exécution du présent contrat relève de la compétence exclusive des "
    "tribunaux marocains."
)

CONTRAT_BODY_AR = (
    "بين الموقعين أدناه، من جهة {partie_a}، ومن جهة أخرى {partie_b}، تم "
    "الاتفاق على ما يلي: المادة 1 - موضوع العقد. المادة 2 - التزامات "
    "الأطراف. المادة 3 - المدة والفسخ. المادة 4 - النزاعات: كل نزاع يتعلق "
    "بتنفيذ هذا العقد يخضع للاختصاص الحصري للمحاكم المغربية."
)


def _write_document(
    source_slug: str,
    filename_stem: str,
    text: str,
    meta: dict,
) -> None:
    folder = RAW_DIR / source_slug
    folder.mkdir(parents=True, exist_ok=True)
    text_path = folder / f"{filename_stem}.txt"
    meta_path = folder / f"{filename_stem}.txt.meta.json"
    text_path.write_text(text, encoding="utf-8")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_bulletin_officiel(n: int) -> None:
    for i in range(1, n + 1):
        article_no = i
        is_ar = i % 3 == 0
        body = BO_ARTICLE_BODY_AR if is_ar else BO_ARTICLE_BODY_FR
        heading = f"المادة {article_no}" if is_ar else f"Article {article_no}"
        text = f"{heading}\n\n{body}"
        stem = f"bo-dahir-65-99-art{article_no:03d}"
        _write_document(
            "bulletin_officiel",
            stem,
            text,
            {
                "doc_id": stem,
                "title": f"Dahir n° 1-03-194 - Code du Travail - {heading}",
                "source": "Bulletin Officiel",
                "date": f"200{3 + (i % 6)}-01-{(i % 28) + 1:02d}",
                "category": BO_CATEGORIES_FR[i % len(BO_CATEGORIES_FR)],
                "language": "ar" if is_ar else "fr",
            },
        )


def generate_jurisprudence(n: int) -> None:
    for i in range(1, n + 1):
        is_ar = i % 4 == 0
        juridiction = JURISPRUDENCE_JURIDICTIONS[i % len(JURISPRUDENCE_JURIDICTIONS)]
        body = JURISPRUDENCE_BODY_AR if is_ar else JURISPRUDENCE_BODY_FR
        case_no = f"{1000 + i}/{2018 + (i % 6)}"
        text = f"{juridiction} - Arrêt n° {case_no}\n\n{body}"
        stem = f"jur-{2018 + (i % 6)}-{1000 + i}"
        _write_document(
            "jurisprudence",
            stem,
            text,
            {
                "doc_id": stem,
                "title": f"{juridiction} - Arrêt n° {case_no}",
                "source": "Jurisprudence",
                "date": f"{2018 + (i % 6)}-06-{(i % 28) + 1:02d}",
                "category": "Droit du travail" if i % 2 == 0 else "Droit civil",
                "language": "ar" if is_ar else "fr",
            },
        )


def generate_contrats_types(n: int) -> None:
    for i in range(1, n + 1):
        is_ar = i % 3 == 1
        contrat_type = CONTRAT_TYPES[i % len(CONTRAT_TYPES)]
        body_template = CONTRAT_BODY_AR if is_ar else CONTRAT_BODY_FR
        body = body_template.format(
            partie_a=f"Partie A n°{i}", partie_b=f"Partie B n°{i}"
        )
        text = f"{contrat_type} (modèle n°{i})\n\n{body}"
        stem = f"contrat-{contrat_type.lower().replace(' ', '-')[:30]}-{i:03d}"
        _write_document(
            "contrats_types",
            stem,
            text,
            {
                "doc_id": stem,
                "title": f"{contrat_type} - Modèle n°{i}",
                "source": "Contrat Type",
                "date": f"{2020 + (i % 5)}-03-{(i % 28) + 1:02d}",
                "category": "Droit des affaires",
                "language": "ar" if is_ar else "fr",
            },
        )


def generate_corpus(total: int) -> None:
    """Split `total` roughly evenly across the 3 sources (min 50, max 100)."""
    total = max(50, min(100, total))
    per_source = total // 3
    remainder = total - per_source * 3

    logger.info("Generating synthetic corpus: %d documents (~%d per source)", total, per_source)
    generate_bulletin_officiel(per_source + (1 if remainder > 0 else 0))
    generate_jurisprudence(per_source + (1 if remainder > 1 else 0))
    generate_contrats_types(per_source)
    logger.info("Synthetic corpus written to %s", RAW_DIR.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic M1 sample corpus")
    parser.add_argument("--count", type=int, default=60, help="Total documents (50-100)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    generate_corpus(args.count)


if __name__ == "__main__":
    main()
