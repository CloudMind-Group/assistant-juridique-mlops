"""Dependency-free BM25 retrieval with Unicode-aware legal tokenisation."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Sequence

from src.m2_rag.models import LegalChunk, RetrievedChunk

_WORD_RE = re.compile(r"[^\W_]+(?:[-./][^\W_]+)*", re.UNICODE)


def lexical_tokens(text: str) -> list[str]:
    return _WORD_RE.findall(unicodedata.normalize("NFKC", text).casefold())


class BM25Index:
    def __init__(self, chunks: Sequence[LegalChunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self.term_frequencies = [Counter(lexical_tokens(chunk.text)) for chunk in self.chunks]
        self.lengths = [sum(frequencies.values()) for frequencies in self.term_frequencies]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        document_frequency: dict[str, int] = defaultdict(int)
        for frequencies in self.term_frequencies:
            for term in frequencies:
                document_frequency[term] += 1
        count = len(self.chunks)
        self.idf = {
            term: math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def search(
        self, query: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[RetrievedChunk]:
        filters = filters or {}
        query_terms = lexical_tokens(query)
        results: list[RetrievedChunk] = []
        for chunk, frequencies, length in zip(self.chunks, self.term_frequencies, self.lengths):
            if any(getattr(chunk, key, chunk.metadata.get(key)) != value for key, value in filters.items()):
                continue
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                normalizer = frequency + self.k1 * (
                    1 - self.b + self.b * length / (self.average_length or 1.0)
                )
                score += self.idf.get(term, 0.0) * frequency * (self.k1 + 1) / normalizer
            if score > 0:
                results.append(
                    RetrievedChunk(
                        doc_id=chunk.doc_id,
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        title=chunk.title,
                        source=chunk.source,
                        date=chunk.date,
                        category=chunk.category,
                        language=chunk.language,
                        score=score,
                        retrieval_method="bm25",
                        chunk_index=chunk.chunk_index,
                        section=chunk.section,
                        metadata=chunk.metadata,
                    )
                )
        return sorted(results, key=lambda item: (-item.score, item.chunk_id))[:limit]
