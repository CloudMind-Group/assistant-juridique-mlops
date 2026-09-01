"""Reproducible corpus-to-index orchestration."""

from __future__ import annotations

from collections.abc import Iterable

from src.m2_rag.chunking import Tokenizer, chunk_document
from src.m2_rag.config import ChunkingConfig
from src.m2_rag.embeddings import Embedder
from src.m2_rag.models import LegalChunk, LegalDocument
from src.m2_rag.vector_store import VectorStore


def build_chunks(
    documents: Iterable[LegalDocument],
    config: ChunkingConfig = ChunkingConfig(),
    tokenizer: Tokenizer | None = None,
) -> list[LegalChunk]:
    return [
        chunk
        for document in documents
        for chunk in chunk_document(document, config, tokenizer)
    ]


def index_chunks(
    chunks: list[LegalChunk], embedder: Embedder, store: VectorStore, *, batch_size: int = 32
) -> int:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        vectors = embedder.embed_documents([chunk.text for chunk in batch])
        store.upsert(batch, vectors)
    return len(chunks)
