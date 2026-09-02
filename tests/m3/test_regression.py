from src.m3_tracking.regression import (
    RegressionThresholds,
    check_regression,
)


def test_regression_passes_when_metrics_are_stable():
    baseline = {
        "faithfulness": 0.90,
        "answer_relevancy": 0.88,
        "context_precision": 0.85,
        "context_recall": 0.84,
    }

    candidate = {
        "faithfulness": 0.89,
        "answer_relevancy": 0.87,
        "context_precision": 0.84,
        "context_recall": 0.83,
    }

    result = check_regression(baseline, candidate)

    assert result.passed is True
    assert result.regressions == {}


def test_regression_detects_large_drop():
    baseline = {
        "faithfulness": 0.90,
        "answer_relevancy": 0.88,
    }

    candidate = {
        "faithfulness": 0.70,
        "answer_relevancy": 0.87,
    }

    result = check_regression(baseline, candidate)

    assert result.passed is False
    assert "faithfulness" in result.regressions


def test_custom_threshold():
    baseline = {"faithfulness": 0.90}
    candidate = {"faithfulness": 0.87}

    thresholds = RegressionThresholds(
        faithfulness=0.02,
    )

    result = check_regression(
        baseline,
        candidate,
        thresholds,
    )

    assert result.passed is False
