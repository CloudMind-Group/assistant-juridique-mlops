"""Optional reranking interfaces; disabled by default for light mode."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol, Sequence

from src.m2_rag.lexical import lexical_tokens
from src.m2_rag.models import RetrievedChunk


class Reranker(Protocol):
    @property
    def model_version(self) -> str: ...

    def rerank(
        self, question: str, chunks: Sequence[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]: ...


class LexicalOverlapReranker:
    """Deterministic test/light reranker, not a cross-encoder quality claim."""

    model_version = "lexical-overlap-v1"

    def rerank(
        self, question: str, chunks: Sequence[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        query = set(lexical_tokens(question))
        rescored = [
            replace(chunk, score=float(len(query.intersection(lexical_tokens(chunk.text)))))
            for chunk in chunks
        ]
        return sorted(rescored, key=lambda item: (-item.score, item.chunk_id))[:limit]


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        *,
        device: str = "cpu",
        model: object | None = None,
    ) -> None:
        if model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for cross-encoder reranking"
                ) from exc
            model = CrossEncoder(model_name, device=device)
        self._model = model
        self._model_version = model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    def rerank(
        self, question: str, chunks: Sequence[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = self._model.predict([(question, chunk.text) for chunk in chunks])
        rescored = [replace(chunk, score=float(score)) for chunk, score in zip(chunks, scores)]
        return sorted(rescored, key=lambda item: (-item.score, item.chunk_id))[:limit]
