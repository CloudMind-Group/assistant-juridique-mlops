import json
from pathlib import Path

import pytest

from src.m2_rag.corpus import (
    CorpusContractError,
    filter_documents,
    load_m1_corpus,
    validate_filter_fields,
)


def _write_corpus(root: Path, records: list[dict]) -> Path:
    processed = root / "data" / "processed"
    (processed / "documents").mkdir(parents=True)
    for record in records:
        (root / record["file_path"]).write_text("Article 1\nTexte juridique valide.", encoding="utf-8")
    (processed / "metadata.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records), encoding="utf-8"
    )
    return processed


def _record(doc_id: str = "opaque id interdit") -> dict:
    return {
        "doc_id": doc_id,
        "title": "Titre",
        "source": "Bulletin Officiel",
        "date": "2024-01-01",
        "category": "Droit civil",
        "language": "fr",
        "file_path": f"data/processed/documents/{doc_id}.txt",
        "anonymized": False,
    }


def test_loads_real_m1_contract_and_tracking_fields(tmp_path: Path):
    record = _record("arbitrary-id-42")
    processed = _write_corpus(tmp_path, [record])
    documents = load_m1_corpus(processed, repo_root=tmp_path)
    assert documents[0].doc_id == "arbitrary-id-42"
    assert documents[0].metadata["anonymized"] is False


def test_rejects_duplicate_doc_id(tmp_path: Path):
    record = _record("same-id")
    processed = _write_corpus(tmp_path, [record, record])
    with pytest.raises(CorpusContractError, match="duplicate doc_id"):
        load_m1_corpus(processed, repo_root=tmp_path)


def test_optional_jurisdiction_fixture_is_preserved_and_filterable(tmp_path: Path):
    first = _record("fixture-rabat")
    first["jurisdiction"] = "Rabat"
    second = _record("fixture-casa")
    second["jurisdiction"] = "Casablanca"
    processed = _write_corpus(tmp_path, [first, second])
    documents = load_m1_corpus(processed, repo_root=tmp_path)
    validate_filter_fields({"jurisdiction": "Rabat", "date": "2024-01-01"})
    assert documents[0].metadata["jurisdiction"] == "Rabat"
    assert [item.doc_id for item in filter_documents(
        documents, {"jurisdiction": "Rabat", "date": "2024-01-01"}
    )] == ["fixture-rabat"]


def test_unknown_filter_field_is_rejected():
    with pytest.raises(CorpusContractError, match="invented_field"):
        validate_filter_fields({"invented_field": "value"})
