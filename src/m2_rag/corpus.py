"""Strict reader for the on-disk M1 → M2 contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from src.m1_ingestion.metadata_schema import DocumentMetadata
from src.m2_rag.models import LegalDocument


class CorpusContractError(ValueError):
    """Raised when an M1 output cannot safely be consumed."""


def _safe_repo_path(repo_root: Path, relative_path: str) -> Path:
    candidate = (repo_root / relative_path).resolve()
    root = repo_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise CorpusContractError(f"file_path escapes repository root: {relative_path}")
    return candidate


def load_m1_corpus(
    processed_dir: Path = Path("data/processed"), *, repo_root: Path = Path(".")
) -> list[LegalDocument]:
    metadata_path = processed_dir / "metadata.jsonl"
    if not metadata_path.is_absolute():
        metadata_path = repo_root / metadata_path
    if not metadata_path.exists():
        raise FileNotFoundError(f"M1 metadata not found: {metadata_path}")

    documents: list[LegalDocument] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(
        metadata_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            raw: dict[str, Any] = json.loads(raw_line)
            metadata = DocumentMetadata.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CorpusContractError(
                f"invalid metadata at {metadata_path}:{line_number}: {exc}"
            ) from exc
        if metadata.doc_id in seen:
            raise CorpusContractError(f"duplicate doc_id: {metadata.doc_id}")
        seen.add(metadata.doc_id)
        text_path = _safe_repo_path(repo_root, metadata.file_path)
        if not text_path.is_file():
            raise CorpusContractError(
                f"missing text for doc_id {metadata.doc_id}: {metadata.file_path}"
            )
        text = text_path.read_text(encoding="utf-8").strip()
        if not text:
            raise CorpusContractError(f"empty text for doc_id {metadata.doc_id}")
        core_fields = {
            "doc_id", "title", "source", "date", "category", "language", "file_path"
        }
        tracking = {key: value for key, value in raw.items() if key not in core_fields}
        documents.append(
            LegalDocument(
                doc_id=metadata.doc_id,
                title=metadata.title,
                source=str(metadata.source),
                date=metadata.date,
                category=metadata.category,
                language=str(metadata.language),
                text=text,
                metadata=tracking,
            )
        )
    if not documents:
        raise CorpusContractError("M1 corpus contains no metadata records")
    return documents


def validate_filter_fields(filters: dict[str, Any]) -> None:
    allowed = {"doc_id", "source", "date", "category", "language"}
    unknown = set(filters) - allowed
    if unknown:
        raise CorpusContractError(f"unsupported metadata filters: {sorted(unknown)}")


def filter_documents(
    documents: Iterable[LegalDocument], filters: dict[str, Any]
) -> list[LegalDocument]:
    validate_filter_fields(filters)
    return [
        document
        for document in documents
        if all(getattr(document, key) == value for key, value in filters.items())
    ]
