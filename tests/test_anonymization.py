"""M8 — regression tests for PII removal in the M1 ingestion pipeline.

Two things are guarded here:

1. Personal data never reaches ``data/processed/``. The pipeline is the only
   place where removal is still a cheap text edit; once M2 has embedded a
   document, removing an individual means rebuilding the index.
2. Legal references survive. A masking rule that eats article, docket or
   registry numbers would corrupt the citations the assistant is built to
   produce — a silent failure that is worse than no masking at all.

Run: ``python -m pytest tests/ -v``
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from src.m1_ingestion.anonymization_schema import (
    DEFAULT_RULE_SET,
    PIIType,
    anonymize_document,
    anonymize_text,
    detect_pii,
)
from src.m1_ingestion.ingest import IngestionPipeline, build_metadata, make_doc_id

# --------------------------------------------------------------------------
# Rule precision: what must be masked
# --------------------------------------------------------------------------

MUST_MASK = [
    ("Le requérant, titulaire de la CIN AB123456, demeurant à Rabat", "AB123456"),
    ("Monsieur Ahmed Benali, CIN A 123456", "A 123456"),
    ("porteur de la carte nationale n° AB12345", "AB12345"),
    ("Monsieur Ahmed Benali comparaît en personne", "Ahmed Benali"),
    ("Maître Salma Tazi, avocate au barreau", "Salma Tazi"),
    ("Le salarié Youssef Idrissi a été licencié", "Youssef Idrissi"),
    ("Témoin : Rachid El Amrani, âgé de 42 ans", "Rachid El Amrani"),
    ("ENTRE : Karim Alaoui, demeurant à Rabat", "Karim Alaoui"),
    ("Contact : a.benali@cabinet.ma pour toute notification", "a.benali@cabinet.ma"),
    ("joignable au 0612345678 selon le dossier", "0612345678"),
]


def test_personal_data_is_removed():
    for text, secret in MUST_MASK:
        assert secret not in anonymize_text(text), (
            f"{secret!r} survived anonymisation in {text!r}"
        )


# --------------------------------------------------------------------------
# Rule precision: what must survive
# --------------------------------------------------------------------------

MUST_SURVIVE = [
    # Amounts: "de 150000" used to be read as a CIN, which silently deleted
    # every award and penalty from the judgments.
    "La somme de 150000 dirhams à titre de dommages-intérêts",
    "Dossier n° 123456 - Cour de Cassation",
    "Registre de commerce RC123456",
    "Bulletin Officiel BO 12345 du 3 janvier",
    "Référence RG 98765/2023",
    "Article 24 du Code du Travail",
    "Vu le dahir n° 1-58-250 du 6 septembre 1958",
    "Conformément à la loi n° 65-99 relative au Code du Travail",
    # Institutions are not personal data and are required for citation.
    "Cour d'Appel de Casablanca",
    "Tribunal de Première Instance de Fès",
]


def test_legal_references_survive():
    for text in MUST_SURVIVE:
        assert anonymize_text(text) == text, (
            f"anonymisation altered a legal reference: {text!r} -> "
            f"{anonymize_text(text)!r}"
        )


def test_masking_preserves_procedural_role():
    """The role carries the legal meaning and must outlive the name."""
    masked = anonymize_text("Le salarié Youssef Idrissi a été licencié")
    assert "salarié" in masked
    assert "licencié" in masked
    assert "[NOM]" in masked


def test_arabic_names_are_masked():
    masked = anonymize_text("حيث أن الشاهد رشيد العمراني أدلى بشهادته")
    assert "رشيد العمراني" not in masked
    assert "الشاهد" in masked


def test_detect_reports_positions_that_match_the_text():
    text = "Le salarié Youssef Idrissi a été licencié"
    for match in detect_pii(text):
        assert text[match.start : match.end] == match.value


def test_report_lists_only_applied_masks():
    text = "Le requérant, titulaire de la CIN AB123456, demeurant à Rabat"
    masked, applied = anonymize_document(text)
    assert masked != text
    assert applied, "expected at least one applied mask"
    assert all(m.pii_type == PIIType.CIN for m in applied)


def test_ruleset_regexes_all_compile():
    for rule in DEFAULT_RULE_SET.rules:
        rule.compiled()


# --------------------------------------------------------------------------
# Metadata must not carry personal data either
# --------------------------------------------------------------------------


@contextlib.contextmanager
def _sandbox():
    """Run inside a throwaway cwd.

    DocumentMetadata rejects absolute file_path values, so the pipeline is
    always driven with paths relative to the working directory — as the CLI
    and the Airflow DAG do. The tests mirror that.
    """
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


def test_doc_id_does_not_leak_the_file_name():
    """A file named after a party must not put that name in the identifier."""
    with _sandbox():
        raw_dir = Path("raw")
        source = raw_dir / "jurisprudence" / "arret_ahmed_benali_2024.txt"
        source.parent.mkdir(parents=True)
        source.write_text("contenu", encoding="utf-8")

        doc_id = make_doc_id(source, raw_dir)

        assert "ahmed" not in doc_id.lower()
        assert "benali" not in doc_id.lower()
        assert doc_id.startswith("jurisprudence-")


def test_title_falls_back_to_source_not_file_name():
    with _sandbox():
        raw_dir = Path("raw")
        source = raw_dir / "jurisprudence" / "arret_ahmed_benali_2024.txt"
        source.parent.mkdir(parents=True)
        source.write_text("contenu", encoding="utf-8")

        meta = build_metadata(source, raw_dir, Path("out"), "contenu du jugement")

        assert "Benali" not in meta.title
        assert "Jurisprudence" in meta.title


# --------------------------------------------------------------------------
# End to end: the pipeline itself
# --------------------------------------------------------------------------

JUDGMENT = (
    "Attendu que Monsieur Ahmed Benali, titulaire de la CIN AB123456, "
    "demeurant à Rabat, joignable au 0612345678, a saisi la Cour d'Appel "
    "de Casablanca ; Attendu que les pièces établissent l'absence de "
    "procédure disciplinaire régulière ; Par ces motifs, la Cour déclare "
    "le licenciement abusif et condamne l'employeur au versement de "
    "150000 dirhams au titre de l'article 41 du Code du Travail."
)

SECRETS = ["Ahmed Benali", "AB123456", "0612345678"]
KEEP = ["Cour d'Appel", "150000", "article 41", "licenciement abusif"]


def _run_pipeline(*, anonymise: bool) -> tuple[Path, str]:
    raw_dir = Path("raw")
    out_dir = Path("processed")
    doc = raw_dir / "jurisprudence" / "arret_ahmed_benali_2024.txt"
    doc.parent.mkdir(parents=True)
    doc.write_text(JUDGMENT, encoding="utf-8")
    doc.with_suffix(".txt.meta.json").write_text(
        json.dumps({"date": "2024-03-12", "category": "Droit du travail"}),
        encoding="utf-8",
    )

    IngestionPipeline(raw_dir, out_dir, anonymise=anonymise).run()
    written = list((out_dir / "documents").glob("*.txt"))
    assert len(written) == 1, f"expected one processed document, got {written}"
    return out_dir, written[0].read_text(encoding="utf-8")


def test_pipeline_writes_no_personal_data():
    with _sandbox():
        _, content = _run_pipeline(anonymise=True)
        for secret in SECRETS:
            assert secret not in content, f"{secret!r} reached data/processed"


def test_pipeline_preserves_the_legal_content():
    with _sandbox():
        _, content = _run_pipeline(anonymise=True)
        for kept in KEEP:
            assert kept in content, f"{kept!r} was lost during anonymisation"


def test_metadata_index_carries_no_personal_data():
    with _sandbox():
        out_dir, _ = _run_pipeline(anonymise=True)
        index = (out_dir / "metadata.jsonl").read_text(encoding="utf-8")
        for secret in SECRETS + ["benali"]:
            assert secret.lower() not in index.lower(), (
                f"{secret!r} reached the metadata index"
            )


def test_opt_out_is_honoured_and_is_the_only_way_to_keep_pii():
    """Guards the default: PII survives only when explicitly asked for."""
    with _sandbox():
        _, content = _run_pipeline(anonymise=False)
        assert "Ahmed Benali" in content
