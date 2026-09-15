"""Citation construction and deterministic grounding validation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.m2_rag.models import Citation, RetrievedChunk


class GroundingError(ValueError):
    pass


_CITATION_MARKER_RE = re.compile(r"\[chunk_id:([^\]\s]+)\]")


def citation_from_chunk(chunk: RetrievedChunk, *, excerpt_chars: int = 500) -> Citation:
    excerpt = " ".join(chunk.text.split())
    if len(excerpt) > excerpt_chars:
        excerpt = excerpt[: excerpt_chars - 1].rstrip() + "…"
    return Citation(
        doc_id=chunk.doc_id,
        chunk_id=chunk.chunk_id,
        title=chunk.title,
        source=chunk.source,
        date=chunk.date,
        category=chunk.category,
        language=chunk.language,
        excerpt=excerpt,
        score=chunk.score,
    )


def validate_citation_ids(
    citation_ids: Sequence[str], retrieved_chunks: Sequence[RetrievedChunk]
) -> list[RetrievedChunk]:
    if not citation_ids:
        raise GroundingError("generated legal answer has no citation")
    available = {chunk.chunk_id: chunk for chunk in retrieved_chunks}
    unknown = set(citation_ids) - set(available)
    if unknown:
        raise GroundingError(f"generated answer cites unknown chunks: {sorted(unknown)}")
    seen: set[str] = set()
    return [
        available[chunk_id]
        for chunk_id in citation_ids
        if not (chunk_id in seen or seen.add(chunk_id))
    ]


def validate_generated_answer(
    answer: str,
    citation_ids: Sequence[str],
    retrieved_chunks: Sequence[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Validate citation provenance; this does not prove semantic entailment."""
    if not answer.strip():
        raise GroundingError("generated answer is empty")
    cited_chunks = validate_citation_ids(citation_ids, retrieved_chunks)
    markers = _CITATION_MARKER_RE.findall(answer)
    if not markers:
        raise GroundingError("generated legal answer has no visible citation marker")
    available = {chunk.chunk_id for chunk in retrieved_chunks}
    unknown = set(markers) - available
    if unknown:
        raise GroundingError(f"generated answer contains unknown citation markers: {sorted(unknown)}")
    if set(markers) != set(citation_ids):
        raise GroundingError("visible citation markers and citation_ids disagree")
    return cited_chunks
