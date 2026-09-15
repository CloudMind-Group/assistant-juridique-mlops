"""Tests for M3 model card generation."""

from __future__ import annotations

import pytest

from src.m3_tracking.model_card import (
    build_model_card,
    render_model_card,
)


def test_build_model_card() -> None:
    card = build_model_card(
        model_name="assistant-juridique-rag",
        version="3",
        dataset_version="dvc-hash-123",
        description="RAG juridique multilingue",
        metrics={
            "faithfulness": 0.95,
            "hallucination_rate": 0.02,
        },
        limitations=[
            "Ne remplace pas un conseil juridique professionnel.",
            "Qualité dépendante du corpus indexé.",
        ],
    )

    assert card.model_name == "assistant-juridique-rag"
    assert card.version == "3"
    assert card.dataset_version == "dvc-hash-123"
    assert card.metrics["faithfulness"] == 0.95
    assert len(card.limitations) == 2
    assert card.created_at


def test_render_model_card() -> None:
    card = build_model_card(
        model_name="assistant-juridique-rag",
        version="4",
        dataset_version="dvc-hash-456",
        description="Candidate RAG",
        metrics={"faithfulness": 0.96},
        limitations=["Évaluation experte encore limitée."],
    )

    markdown = render_model_card(card)

    assert "# Model Card — assistant-juridique-rag" in markdown
    assert "## Version" in markdown
    assert "4" in markdown
    assert "## Dataset version" in markdown
    assert "dvc-hash-456" in markdown
    assert "0.9600" in markdown
    assert "Évaluation experte encore limitée." in markdown


def test_model_card_requires_model_name() -> None:
    with pytest.raises(ValueError, match="model_name is required"):
        build_model_card(
            model_name="",
            version="1",
            dataset_version="dvc-hash-123",
            description="test",
            metrics={"faithfulness": 0.95},
            limitations=["Limitation connue."],
        )


def test_model_card_requires_version() -> None:
    with pytest.raises(ValueError, match="version is required"):
        build_model_card(
            model_name="assistant-juridique-rag",
            version="",
            dataset_version="dvc-hash-123",
            description="test",
            metrics={"faithfulness": 0.95},
            limitations=["Limitation connue."],
        )


def test_model_card_requires_dataset_version() -> None:
    with pytest.raises(ValueError, match="dataset_version is required"):
        build_model_card(
            model_name="assistant-juridique-rag",
            version="1",
            dataset_version="",
            description="test",
            metrics={"faithfulness": 0.95},
            limitations=["Limitation connue."],
        )


def test_model_card_requires_description() -> None:
    with pytest.raises(ValueError, match="description is required"):
        build_model_card(
            model_name="assistant-juridique-rag",
            version="1",
            dataset_version="dvc-hash-123",
            description="",
            metrics={"faithfulness": 0.95},
            limitations=["Limitation connue."],
        )


def test_model_card_requires_metrics() -> None:
    with pytest.raises(ValueError, match="at least one metric is required"):
        build_model_card(
            model_name="assistant-juridique-rag",
            version="1",
            dataset_version="dvc-hash-123",
            description="test",
            metrics={},
            limitations=["Limitation connue."],
        )


def test_model_card_requires_at_least_one_limitation() -> None:
    with pytest.raises(
        ValueError,
        match="at least one limitation is required",
    ):
        build_model_card(
            model_name="assistant-juridique-rag",
            version="1",
            dataset_version="dvc-hash-123",
            description="test",
            metrics={"faithfulness": 0.95},
            limitations=[],
        )


def test_model_card_rejects_blank_limitations() -> None:
    with pytest.raises(
        ValueError,
        match="at least one limitation is required",
    ):
        build_model_card(
            model_name="assistant-juridique-rag",
            version="1",
            dataset_version="dvc-hash-123",
            description="test",
            metrics={"faithfulness": 0.95},
            limitations=["   ", ""],
        )
