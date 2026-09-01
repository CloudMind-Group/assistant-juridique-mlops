"""Optional M3-facing hooks; M2 never imports MLflow directly."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from src.m2_rag.config import RAGConfig
from src.m2_rag.models import RAGRequest, RAGResponse


class TrackingHook(Protocol):
    def log_parameters(self, parameters: dict[str, Any]) -> None: ...
    def log_metrics(self, metrics: dict[str, float]) -> None: ...
    def log_query(self, request: RAGRequest, response: RAGResponse) -> None: ...


def experiment_parameters(config: RAGConfig, *, embedding_dimension: int) -> dict[str, Any]:
    return {
        "embedding_model": config.embedding_model,
        "embedding_dimension": embedding_dimension,
        "chunk_size": config.chunking.target_tokens,
        "chunk_overlap": config.chunking.overlap_tokens,
        "chunker_version": config.chunking.version,
        "chunking_version": config.chunking.version,
        "retrieval_method": "hybrid_rrf",
        "top_k": config.top_k,
        "candidate_k": config.candidate_k,
        "reranker": config.reranker_model if config.reranker_enabled else "disabled",
        "prompt_version": config.prompt_version,
        "llm_model": config.llm_model,
        "available_metrics": ["recall_at_k", "latency_min_ms", "latency_mean_ms", "latency_p50_ms", "latency_p95_ms"],
        "latencies": ["retrieval_ms", "generation_ms", "total_ms"],
    }


@dataclass
class InMemoryTrackingHook:
    """Test adapter and reference contract for M3's future MLflow adapter."""

    parameters: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, float]] = field(default_factory=list)
    queries: list[tuple[RAGRequest, RAGResponse]] = field(default_factory=list)

    def log_parameters(self, parameters: dict[str, Any]) -> None:
        self.parameters.append(dict(parameters))

    def log_metrics(self, metrics: dict[str, float]) -> None:
        self.metrics.append(dict(metrics))

    def log_query(self, request: RAGRequest, response: RAGResponse) -> None:
        self.queries.append((request, response))
