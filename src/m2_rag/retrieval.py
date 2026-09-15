"""Dense retrieval, reciprocal-rank fusion, and the hybrid pipeline."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol, Sequence

from src.m2_rag.embeddings import Embedder
from src.m2_rag.lexical import BM25Index
from src.m2_rag.models import RetrievedChunk
from src.m2_rag.reranker import Reranker
from src.m2_rag.vector_store import VectorStore


class FusionStrategy(Protocol):
    def fuse(
        self, rankings: Sequence[tuple[Sequence[RetrievedChunk], float]], limit: int
    ) -> list[RetrievedChunk]: ...


class ReciprocalRankFusion:
    def __init__(self, rank_constant: int = 60) -> None:
        if rank_constant <= 0:
            raise ValueError("rank_constant must be positive")
        self.rank_constant = rank_constant

    def fuse(
        self, rankings: Sequence[tuple[Sequence[RetrievedChunk], float]], limit: int
    ) -> list[RetrievedChunk]:
        scores: dict[str, float] = {}
        chunks: dict[str, RetrievedChunk] = {}
        methods: dict[str, set[str]] = {}
        for ranking, weight in rankings:
            if weight <= 0:
                continue
            for rank, chunk in enumerate(ranking, start=1):
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + weight / (
                    self.rank_constant + rank
                )
                chunks[chunk.chunk_id] = chunk
                methods.setdefault(chunk.chunk_id, set()).add(chunk.retrieval_method)
        ordered = sorted(scores, key=lambda key: (-scores[key], key))[:limit]
        return [
            replace(
                chunks[key],
                score=scores[key],
                retrieval_method="+".join(sorted(methods[key])),
            )
            for key in ordered
        ]


class DenseRetriever:
    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    def search(
        self, question: str, limit: int, filters: dict[str, Any] | None = None
    ) -> list[RetrievedChunk]:
        return self.store.search(self.embedder.embed_query(question), limit, filters)


class HybridRetriever:
    def __init__(
        self,
        lexical: BM25Index,
        dense: DenseRetriever,
        fusion: FusionStrategy,
        *,
        candidate_k: int = 24,
        top_k: int = 8,
        dense_weight: float = 1.0,
        lexical_weight: float = 1.0,
        reranker: Reranker | None = None,
    ) -> None:
        if candidate_k < top_k or top_k <= 0:
            raise ValueError("candidate_k must be >= top_k > 0")
        self.lexical = lexical
        self.dense = dense
        self.fusion = fusion
        self.candidate_k = candidate_k
        self.top_k = top_k
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight
        self.reranker = reranker

    def retrieve(
        self,
        question: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        requested = top_k or self.top_k
        dense = self.dense.search(question, self.candidate_k, filters)
        lexical = self.lexical.search(question, self.candidate_k, filters)
        candidates = self.fusion.fuse(
            [(dense, self.dense_weight), (lexical, self.lexical_weight)], self.candidate_k
        )
        if self.reranker is not None:
            candidates = self.reranker.rerank(question, candidates, self.candidate_k)
        return candidates[:requested]
