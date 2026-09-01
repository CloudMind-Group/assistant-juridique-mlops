"""Model card generation for M3 model governance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ModelCard:
    model_name: str
    version: str
    description: str
    metrics: dict[str, float]
    limitations: list[str]
    created_at: str


def build_model_card(
    model_name: str,
    version: str,
    description: str,
    metrics: dict[str, float],
    limitations: list[str] | None = None,
) -> ModelCard:
    """Build a traceable model card from evaluation results."""

    if not model_name.strip():
        raise ValueError("model_name is required")

    if not version.strip():
        raise ValueError("version is required")

    if not metrics:
        raise ValueError("at least one metric is required")

    return ModelCard(
        model_name=model_name,
        version=version,
        description=description,
        metrics=dict(metrics),
        limitations=list(limitations or []),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def render_model_card(card: ModelCard) -> str:
    """Render a model card as Markdown."""

    metric_lines = "\n".join(
        f"- {name}: {value:.4f}"
        for name, value in sorted(card.metrics.items())
    )

    limitation_lines = (
        "\n".join(f"- {item}" for item in card.limitations)
        if card.limitations
        else "- None documented"
    )

    return f"""# Model Card — {card.model_name}

## Version
{card.version}

## Description
{card.description}

## Evaluation metrics
{metric_lines}

## Limitations
{limitation_lines}

## Generated at
{card.created_at}
"""
