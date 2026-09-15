"""Composition helpers that keep M5 independent from retrieval internals."""

from __future__ import annotations

from collections.abc import Sequence

from src.m2_rag.config import RAGConfig
from src.m2_rag.embeddings import DeterministicFakeEmbedder
from src.m2_rag.generator import FakeGroundedGenerator, Generator
from src.m2_rag.indexing import build_chunks, index_chunks
from src.m2_rag.lexical import BM25Index
from src.m2_rag.models import LegalDocument
from src.m2_rag.retrieval import DenseRetriever, HybridRetriever, ReciprocalRankFusion
from src.m2_rag.service import RAGService, ScopeGuard
from src.m2_rag.vector_store import InMemoryVectorStore


def build_light_service(
    documents: Sequence[LegalDocument],
    *,
    config: RAGConfig = RAGConfig(),
    generator: Generator | None = None,
    scope_guard: ScopeGuard | None = None,
    embedding_dimension: int = 64,
) -> RAGService:
    """Build the dependency-free deterministic M1-to-RAG smoke pipeline."""
    chunks = build_chunks(documents, config.chunking)
    embedder = DeterministicFakeEmbedder(embedding_dimension)
    store = InMemoryVectorStore(embedder.dimension)
    index_chunks(chunks, embedder, store)
    retriever = HybridRetriever(
        BM25Index(chunks),
        DenseRetriever(embedder, store),
        ReciprocalRankFusion(config.rrf_k),
        candidate_k=config.candidate_k,
        top_k=config.top_k,
        dense_weight=config.dense_weight,
        lexical_weight=config.lexical_weight,
    )
    return RAGService(
        retriever,
        generator or FakeGroundedGenerator(),
        config,
        scope_guard=scope_guard,
    )
