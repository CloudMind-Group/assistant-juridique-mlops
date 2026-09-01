from src.m3_tracking.quality_gate import evaluate_quality_gate


def test_quality_gate_passes():
    baseline = {
        "faithfulness": 0.90,
        "context_recall": 0.85,
    }

    candidate = {
        "faithfulness": 0.91,
        "context_recall": 0.86,
    }

    result = evaluate_quality_gate(
        baseline=baseline,
        candidate=candidate,
        minimum_metrics={
            "faithfulness": 0.85,
            "context_recall": 0.80,
        },
    )

    assert result.passed is True
    assert result.reasons == []


def test_quality_gate_rejects_low_metric():
    result = evaluate_quality_gate(
        baseline={"faithfulness": 0.90},
        candidate={"faithfulness": 0.70},
        minimum_metrics={"faithfulness": 0.85},
    )

    assert result.passed is False
    assert any(
        "faithfulness below minimum" in reason
        for reason in result.reasons
    )


def test_quality_gate_rejects_missing_metric():
    result = evaluate_quality_gate(
        baseline={},
        candidate={},
        minimum_metrics={"faithfulness": 0.85},
    )

    assert result.passed is False
    assert "missing metric: faithfulness" in result.reasons


def test_quality_gate_detects_regression():
    result = evaluate_quality_gate(
        baseline={"faithfulness": 0.95},
        candidate={"faithfulness": 0.80},
    )

    assert result.passed is False
    assert any(
        "regression too large" in reason
        for reason in result.reasons
    )
