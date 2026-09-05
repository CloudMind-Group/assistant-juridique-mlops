"""M1 — tests du contrôle qualité.

`quality.py` est la porte de qualité branchée sur la CI : si elle laisse
passer un corpus abîmé, plus rien en aval ne le rattrape. Elle était
pourtant à 0 % de couverture. Ces tests verrouillent les trois familles de
défauts qu'elle est censée arrêter — métadonnées manquantes, schéma
invalide, contenu vide ou tronqué — plus le cas d'un `metadata.jsonl`
corrompu, qui passait silencieusement avant le correctif.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from src.m1_ingestion.quality import (
    MAX_TOKENS,
    check_document,
    run_quality_check,
    write_report,
)


@contextlib.contextmanager
def _sandbox():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


def _valid_record(doc_id: str = "jur-abc123") -> dict:
    return {
        "doc_id": doc_id,
        "title": "Jurisprudence — 2024-01-01",
        "source": "Jurisprudence",
        "date": "2024-01-01",
        "category": "Droit du travail",
        "language": "fr",
        "file_path": f"out/documents/{doc_id}.txt",
    }


def _write_corpus(records: list[dict], texts: dict[str, str]) -> Path:
    out = Path("out")
    (out / "documents").mkdir(parents=True, exist_ok=True)
    for doc_id, text in texts.items():
        (out / "documents" / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    (out / "metadata.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return out


VALID_TEXT = "Attendu que la rupture du contrat de travail est abusive et injustifiée."


# --------------------------------------------------------------------------
# check_document : les trois familles de défauts
# --------------------------------------------------------------------------


def test_document_valide_passe():
    with _sandbox():
        _write_corpus([_valid_record()], {"jur-abc123": VALID_TEXT})
        result = check_document(_valid_record(), Path("out"))

        assert result.passed
        assert result.errors == []


def test_champ_obligatoire_manquant_est_rejete():
    with _sandbox():
        _write_corpus([], {"jur-abc123": VALID_TEXT})
        record = _valid_record()
        record["title"] = "   "

        result = check_document(record, Path("out"))

        assert not result.passed
        assert any("title" in error for error in result.errors)


def test_schema_invalide_est_rejete():
    with _sandbox():
        _write_corpus([], {"jur-abc123": VALID_TEXT})
        record = _valid_record()
        record["date"] = "01/01/2024"  # format refusé par DocumentMetadata

        result = check_document(record, Path("out"))

        assert not result.passed
        assert any("date" in error for error in result.errors)


def test_source_inconnue_est_rejetee():
    with _sandbox():
        _write_corpus([], {"jur-abc123": VALID_TEXT})
        record = _valid_record()
        record["source"] = "Source Inventée"

        result = check_document(record, Path("out"))

        assert not result.passed


def test_fichier_texte_absent_est_rejete():
    with _sandbox():
        Path("out").mkdir()
        result = check_document(_valid_record(), Path("out"))

        assert not result.passed
        assert any("not found" in error for error in result.errors)


def test_texte_vide_est_rejete():
    with _sandbox():
        _write_corpus([], {"jur-abc123": "   \n  "})
        result = check_document(_valid_record(), Path("out"))

        assert not result.passed
        assert any("empty" in error for error in result.errors)


def test_texte_trop_court_est_rejete():
    with _sandbox():
        _write_corpus([], {"jur-abc123": "Trop court"})
        result = check_document(_valid_record(), Path("out"))

        assert not result.passed
        assert any("too short" in error for error in result.errors)


def test_texte_tres_long_est_un_avertissement_pas_une_erreur():
    with _sandbox():
        _write_corpus([], {"jur-abc123": "mot " * (MAX_TOKENS + 10)})
        result = check_document(_valid_record(), Path("out"))

        assert result.passed, "un texte long ne doit pas bloquer la chaîne"
        assert result.warnings


# --------------------------------------------------------------------------
# run_quality_check : agrégation et robustesse du fichier d'index
# --------------------------------------------------------------------------


def test_rapport_agrege_les_resultats():
    with _sandbox():
        records = [_valid_record("doc-a"), _valid_record("doc-b")]
        records[1]["date"] = "pas-une-date"
        _write_corpus(records, {"doc-a": VALID_TEXT, "doc-b": VALID_TEXT})

        report = run_quality_check(Path("out"))

        assert report.total_documents == 2
        assert report.passed == 1
        assert report.failed == 1
        assert report.pass_rate == 0.5


def test_metadata_absent_leve_une_erreur_explicite():
    with _sandbox():
        Path("out").mkdir()

        with pytest.raises(FileNotFoundError):
            run_quality_check(Path("out"))


def test_json_corrompu_fait_echouer_le_controle():
    """Avant le correctif, la ligne était ignorée et le contrôle passait."""
    with _sandbox():
        _write_corpus([_valid_record()], {"jur-abc123": VALID_TEXT})
        with Path("out/metadata.jsonl").open("a", encoding="utf-8") as f:
            f.write("\nceci n'est pas du JSON\n")

        with pytest.raises(ValueError, match="Malformed JSON"):
            run_quality_check(Path("out"))


def test_lignes_vides_sont_tolerees():
    with _sandbox():
        _write_corpus([_valid_record()], {"jur-abc123": VALID_TEXT})
        with Path("out/metadata.jsonl").open("a", encoding="utf-8") as f:
            f.write("\n\n")

        report = run_quality_check(Path("out"))

        assert report.total_documents == 1


def test_write_report_produit_un_json_lisible():
    with _sandbox():
        _write_corpus([_valid_record()], {"jur-abc123": VALID_TEXT})
        report = run_quality_check(Path("out"))

        path = write_report(report, Path("out"))
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert payload["total_documents"] == 1
        assert payload["passed"] == 1
        assert payload["results"][0]["doc_id"] == "jur-abc123"
