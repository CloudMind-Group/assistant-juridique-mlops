"""Tests for M3 RAGAS evaluation helpers."""

import pytest

from src.m3_tracking.ragas_evaluator import (
    RAGASEvaluationSample,
    build_ragas_records,
    normalize_ragas_metrics,
)


def test_build_ragas_record():
    sample = RAGASEvaluationSample(
        question="Quel est le rôle de la citation ?",
        answer="La réponse doit être fondée sur une source.",
        contexts=[
            "Toute réponse juridique doit être sourcée.",
        ],
        reference="Une réponse doit citer ses sources.",
    )

    records = build_ragas_records([sample])

    assert len(records) == 1

    assert records[0]["user_input"] == (
        "Quel est le rôle de la citation ?"
    )

    assert records[0]["response"] == (
        "La réponse doit être fondée sur une source."
    )

    assert records[0]["retrieved_contexts"] == [
        "Toute réponse juridique doit être sourcée."
    ]

    assert records[0]["reference"] == (
        "Une réponse doit citer ses sources."
    )


def test_reference_is_optional():
    sample = RAGASEvaluationSample(
        question="Question",
        answer="Réponse",
        contexts=["Contexte"],
    )

    record = build_ragas_records([sample])[0]

    assert "reference" not in record


def test_empty_question_is_rejected():
    with pytest.raises(ValueError):
        RAGASEvaluationSample(
            question=" ",
            answer="Réponse",
            contexts=["Contexte"],
        )


def test_empty_contexts_are_rejected():
    with pytest.raises(ValueError):
        RAGASEvaluationSample(
            question="Question",
            answer="Réponse",
            contexts=[],
        )


def test_normalize_ragas_metrics():
    metrics = normalize_ragas_metrics(
        {
            "faithfulness": 0.95,
            "answer_relevancy": "0.91",
            "metadata": {"model": "judge"},
            "missing": None,
        }
    )

    assert metrics == {
        "faithfulness": 0.95,
        "answer_relevancy": 0.91,
    }
