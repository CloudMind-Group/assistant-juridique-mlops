"""M3 evaluation runner linking RAGAS metrics to experiment tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .ragas_evaluator import (
    RAGASEvaluationSample,
    build_ragas_records,
    normalize_ragas_metrics,
)


class MetricTracker(Protocol):
    def log_metrics(self, metrics: dict[str, float]) -> None:
        ...


@dataclass(frozen=True)
class EvaluationResult:
    metrics: dict[str, float]
    sample_count: int


class EvaluationRunner:
    """Run an evaluator and forward normalized metrics to a tracker."""

    def __init__(
        self,
        tracker: MetricTracker,
        evaluator: Callable[[list[dict[str, object]]], dict[str, object]],
    ) -> None:
        self.tracker = tracker
        self.evaluator = evaluator

    def run(
        self,
        samples: list[RAGASEvaluationSample],
    ) -> EvaluationResult:
        if not samples:
            raise ValueError("at least one evaluation sample is required")

        records = build_ragas_records(samples)

        raw_metrics = self.evaluator(records)
        metrics = normalize_ragas_metrics(raw_metrics)

        if not metrics:
            raise ValueError("evaluator returned no numerical metrics")

        self.tracker.log_metrics(metrics)

        return EvaluationResult(
            metrics=metrics,
            sample_count=len(samples),
        )
