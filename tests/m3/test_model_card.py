import pytest

from src.m3_tracking.model_card import (
    build_model_card,
    render_model_card,
)


def test_build_model_card():
    card = build_model_card(
        model_name="assistant-juridique-rag",
        version="v1",
        description="RAG juridique.",
        metrics={
            "faithfulness": 0.92,
            "context_recall": 0.88,
        },
        limitations=[
            "Ne remplace pas un conseil juridique professionnel."
        ],
    )

    assert card.model_name == "assistant-juridique-rag"
    assert card.version == "v1"
    assert card.metrics["faithfulness"] == 0.92


def test_render_model_card():
    card = build_model_card(
        model_name="assistant-juridique-rag",
        version="v1",
        description="RAG juridique.",
        metrics={"faithfulness": 0.92},
    )

    markdown = render_model_card(card)

    assert "# Model Card — assistant-juridique-rag" in markdown
    assert "faithfulness: 0.9200" in markdown
    assert "v1" in markdown


def test_model_card_requires_name():
    with pytest.raises(ValueError):
        build_model_card(
            model_name="",
            version="v1",
            description="test",
            metrics={"faithfulness": 0.9},
        )


def test_model_card_requires_version():
    with pytest.raises(ValueError):
        build_model_card(
            model_name="model",
            version="",
            description="test",
            metrics={"faithfulness": 0.9},
        )


def test_model_card_requires_metrics():
    with pytest.raises(ValueError):
        build_model_card(
            model_name="model",
            version="v1",
            description="test",
            metrics={},
        )
