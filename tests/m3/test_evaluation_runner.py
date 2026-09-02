"""Tests for the M3 evaluation runner."""

import pytest

from src.m3_tracking.evaluation_runner import EvaluationRunner
from src.m3_tracking.ragas_evaluator import RAGASEvaluationSample


class FakeTracker:
    def __init__(self):
        self.metrics = {}

    def log_metrics(self, metrics):
        self.metrics.update(metrics)


def fake_evaluator(records):
    assert len(records) == 1

    return {
        "faithfulness": 0.95,
        "answer_relevancy": 0.91,
        "context_precision": 0.90,
        "context_recall": 0.89,
    }


def test_evaluation_runner_logs_metrics():
    tracker = FakeTracker()

    runner = EvaluationRunner(
        tracker=tracker,
        evaluator=fake_evaluator,
    )

    sample = RAGASEvaluationSample(
        question="Quelle est la règle ?",
        answer="La réponse est fondée sur la source.",
        contexts=["Texte juridique pertinent."],
        reference="Réponse attendue.",
    )

    result = runner.run([sample])

    assert result.sample_count == 1
    assert result.metrics["faithfulness"] == 0.95
    assert result.metrics["context_recall"] == 0.89

    assert tracker.metrics == result.metrics


def test_runner_rejects_empty_samples():
    tracker = FakeTracker()

    runner = EvaluationRunner(
        tracker=tracker,
        evaluator=fake_evaluator,
    )

    with pytest.raises(ValueError):
        runner.run([])


def test_runner_rejects_empty_metrics():
    tracker = FakeTracker()

    runner = EvaluationRunner(
        tracker=tracker,
        evaluator=lambda records: {},
    )

    sample = RAGASEvaluationSample(
        question="Question",
        answer="Réponse",
        contexts=["Contexte"],
    )

    with pytest.raises(ValueError):
        runner.run([sample])
