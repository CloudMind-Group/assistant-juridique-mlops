"""
Metadata schema for Module 1 (Data Ingestion) — assistant-juridique-mlops.

Defines the contract that every ingested legal document must satisfy before
being handed off to Module 2 (Imane — Indexation/Reranking). Validation is
enforced with Pydantic so malformed documents are rejected early, with a
clear error message, instead of silently polluting the processed corpus.
"""

from __future__ import annotations

import re
from datetime import date as date_cls
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# Matches "YYYY-MM-DD" or a bare "YYYY" (some Bulletin Officiel / jurisprudence
# entries only carry a year of publication).
_DATE_PATTERN = re.compile(r"^\d{4}(-\d{2}-\d{2})?$")


class SourceType(str, Enum):
    """The 3 legal sources selected for the M1 sample corpus."""

    BULLETIN_OFFICIEL = "Bulletin Officiel"
    JURISPRUDENCE = "Jurisprudence"
    CONTRAT_TYPE = "Contrat Type"


class Language(str, Enum):
    FR = "fr"
    AR = "ar"


class DocumentMetadata(BaseModel):
    """Metadata sidecar attached to every document in data/processed/.

    Consumed as-is by Module 2 for indexing — do not rename fields without
    coordinating with Imane, since her ingestion pipeline reads this schema
    directly (see README.md in this package).
    """

    doc_id: str = Field(..., min_length=1, description="Unique document ID")
    title: str = Field(..., min_length=1)
    source: SourceType
    date: str = Field(..., description="YYYY-MM-DD or YYYY")
    category: str = Field(..., min_length=1)
    language: Language
    file_path: str = Field(
        ..., description="Path to the clean text file, relative to repo root"
    )

    model_config = {"use_enum_values": True}

    @field_validator("doc_id")
    @classmethod
    def doc_id_no_whitespace(cls, v: str) -> str:
        if re.search(r"\s", v):
            raise ValueError("doc_id must not contain whitespace")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not _DATE_PATTERN.match(v):
            raise ValueError(f"date must match YYYY-MM-DD or YYYY, got {v!r}")
        year = int(v[:4])
        if not (1900 <= year <= date_cls.today().year + 1):
            raise ValueError(f"date year {year} is out of plausible range")
        return v

    @field_validator("file_path")
    @classmethod
    def normalize_file_path(cls, v: str) -> str:
        v = v.replace("\\", "/").strip()
        if v.startswith("/") or re.match(r"^[A-Za-z]:", v):
            raise ValueError("file_path must be a relative path, not absolute")
        return v
