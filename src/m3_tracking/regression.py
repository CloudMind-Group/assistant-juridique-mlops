"""Regression checks for M3 RAG evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegressionThresholds:
    """Maximum tolerated degradation for each metric."""

    faithfulness: float = 0.05
    answer_relevancy: float = 0.05
    context_precision: float = 0.05
    context_recall: float = 0.05


@dataclass(frozen=True)
class RegressionResult:
    passed: bool
    regressions: dict[str, float]


def check_regression(
    baseline: dict[str, float],
    candidate: dict[str, float],
    thresholds: RegressionThresholds | None = None,
) -> RegressionResult:
    """Compare candidate metrics against a reference baseline."""

    thresholds = thresholds or RegressionThresholds()

    threshold_map = {
        "faithfulness": thresholds.faithfulness,
        "answer_relevancy": thresholds.answer_relevancy,
        "context_precision": thresholds.context_precision,
        "context_recall": thresholds.context_recall,
    }

    regressions: dict[str, float] = {}

    for metric, maximum_drop in threshold_map.items():
        if metric not in baseline or metric not in candidate:
            continue

        drop = baseline[metric] - candidate[metric]

        if drop > maximum_drop:
            regressions[metric] = drop

    return RegressionResult(
        passed=not regressions,
        regressions=regressions,
    )
