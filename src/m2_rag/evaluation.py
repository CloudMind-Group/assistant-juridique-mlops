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


@dataclass(frozen=True)
class LatencyReport:
    p50_ms: float
    runs: int
    backend: str
    corpus_size: int
    environment: str


def recall_at_k(
    examples: Sequence[RetrievalExample],
    retrieve: Callable[[str, int], Sequence[RetrievedChunk]],
    *,
    k: int = 8,
) -> float:
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
    query: Callable[[], object], *, runs: int, backend: str, corpus_size: int
) -> LatencyReport:
    if runs <= 0:
        raise ValueError("runs must be positive")
    durations = []
    for _ in range(runs):
        started = perf_counter()
        query()
        durations.append((perf_counter() - started) * 1000)
    return LatencyReport(
        p50_ms=statistics.median(durations),
        runs=runs,
        backend=backend,
        corpus_size=corpus_size,
        environment=f"{platform.system()} {platform.release()} | Python {platform.python_version()}",
    )
