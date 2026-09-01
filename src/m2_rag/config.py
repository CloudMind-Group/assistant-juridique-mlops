"""Configuration objects for M2, with safe CPU-friendly defaults."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    target_tokens: int = 512
    overlap_tokens: int = 64
    version: str = "legal-v1"

    def __post_init__(self) -> None:
        if self.target_tokens <= 0:
            raise ValueError("target_tokens must be positive")
        if self.overlap_tokens < 0 or self.overlap_tokens >= self.target_tokens:
            raise ValueError("overlap_tokens must be in [0, target_tokens)")


@dataclass(frozen=True)
class RAGConfig:
    collection_name: str = "legal_fr_1024"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    llm_model: str = "unconfigured"
    top_k: int = 8
    candidate_k: int = 24
    dense_weight: float = 1.0
    lexical_weight: float = 1.0
    rrf_k: int = 60
    reranker_enabled: bool = False
    prompt_version: str = "v1"
    chunking: ChunkingConfig = ChunkingConfig()

    def __post_init__(self) -> None:
        if self.top_k <= 0 or self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be >= top_k > 0")
        if self.dense_weight < 0 or self.lexical_weight < 0:
            raise ValueError("retrieval weights cannot be negative")
        if self.dense_weight == self.lexical_weight == 0:
            raise ValueError("at least one retrieval weight must be positive")
        if self.rrf_k <= 0:
            raise ValueError("rrf_k must be positive")
