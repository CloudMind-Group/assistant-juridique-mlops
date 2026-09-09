"""Evaluation utilities that refuse to invent metrics without ground truth."""

from __future__ import annotations

import platform
import statistics
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Sequence

from src.m2_rag.models import RetrievedChunk


@dataclass(frozen=True)
class RetrievalExample:
    question: str
    relevant_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("evaluation question must not be empty")
        if not self.relevant_ids or any(not item.strip() for item in self.relevant_ids):
            raise ValueError("relevant_ids must contain non-empty identifiers")


@dataclass(frozen=True)
class LatencyReport:
    min_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    runs: int
    backend: str
    embedder: str
    corpus: str
    chunk_count: int
    environment: str

    @property
    def corpus_size(self) -> int:
        """Backward-compatible alias for reports created before chunk_count."""
        return self.chunk_count


def recall_at_k(
    examples: Sequence[RetrievalExample],
    retrieve: Callable[[str, int], Sequence[RetrievedChunk]],
    *,
    k: int = 8,
) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    if not examples:
        raise ValueError("Recall@k requires a non-empty annotated ground-truth dataset")
    if any(not example.relevant_ids for example in examples):
        raise ValueError("every evaluation example needs at least one relevant id")
    recalls = []
    for example in examples:
        results = retrieve(example.question, k)
        returned = {item.chunk_id for item in results} | {item.doc_id for item in results}
        recalls.append(len(returned & example.relevant_ids) / len(example.relevant_ids))
    return sum(recalls) / len(recalls)


def benchmark_retrieval_latency(
    query: Callable[[], object], *, runs: int, backend: str,
    embedder: str = "not-applicable", corpus: str = "unspecified",
    chunk_count: int | None = None, corpus_size: int | None = None,
) -> LatencyReport:
    if runs <= 0:
        raise ValueError("runs must be positive")
    durations = []
    for _ in range(runs):
        started = perf_counter()
        query()
        durations.append((perf_counter() - started) * 1000)
    count = chunk_count if chunk_count is not None else corpus_size
    if count is None or count < 0:
        raise ValueError("chunk_count must be non-negative")
    ordered = sorted(durations)
    p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999999) - 1))
    return LatencyReport(
        min_ms=min(durations),
        mean_ms=statistics.fmean(durations),
        p50_ms=statistics.median(durations),
        p95_ms=ordered[p95_index],
        runs=runs,
        backend=backend,
        embedder=embedder,
        corpus=corpus,
        chunk_count=count,
        environment=f"{platform.system()} {platform.release()} | Python {platform.python_version()}",
    )
