"""Stable Python contracts shared with the serving and tracking modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LegalDocument:
    doc_id: str
    title: str
    source: str
    date: str
    category: str
    language: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LegalChunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    token_count: int
    section: str | None
    title: str
    source: str
    date: str
    category: str
    language: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedChunk:
    doc_id: str
    chunk_id: str
    text: str
    title: str
    source: str
    date: str
    category: str
    language: str
    score: float
    retrieval_method: str
    chunk_index: int = 0
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Citation:
    doc_id: str
    chunk_id: str
    title: str
    source: str
    date: str
    category: str
    language: str
    excerpt: str
    score: float


@dataclass(frozen=True)
class RAGRequest:
    question: str
    top_k: int | None = None
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    prompt_version: str
    model_version: str
    latencies: dict[str, float]
    refused: bool = False
    refusal_reason: str | None = None
