"""Quality gate for M3 model evaluation and promotion."""

from __future__ import annotations

from dataclasses import dataclass

from .regression import RegressionThresholds, check_regression


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    reasons: list[str]


def evaluate_quality_gate(
    baseline: dict[str, float],
    candidate: dict[str, float],
    minimum_metrics: dict[str, float] | None = None,
    regression_thresholds: RegressionThresholds | None = None,
) -> QualityGateResult:
    """Decide whether a candidate model satisfies M3 quality requirements."""

    minimum_metrics = minimum_metrics or {}
    reasons: list[str] = []

    for metric, minimum in minimum_metrics.items():
        value = candidate.get(metric)

        if value is None:
            reasons.append(f"missing metric: {metric}")
        elif value < minimum:
            reasons.append(
                f"{metric} below minimum: {value:.4f} < {minimum:.4f}"
            )

    regression = check_regression(
        baseline=baseline,
        candidate=candidate,
        thresholds=regression_thresholds,
    )

    for metric, drop in regression.regressions.items():
        reasons.append(
            f"{metric} regression too large: {drop:.4f}"
        )

    return QualityGateResult(
        passed=not reasons,
        reasons=reasons,
    )
