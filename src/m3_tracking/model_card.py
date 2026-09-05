"""Model card generation for M3 model governance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ModelCard:
    """Structured governance artifact describing one model version."""

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
    """Build a traceable model card from evaluation results.

    A model card is considered incomplete when no limitation is declared.
    Governance documentation must describe not only model performance,
    but also known failure modes and usage boundaries.
    """

    if not model_name.strip():
        raise ValueError("model_name is required")

    if not version.strip():
        raise ValueError("version is required")

    if not description.strip():
        raise ValueError("description is required")

    if not metrics:
        raise ValueError("at least one metric is required")

    normalized_limitations = [
        limitation.strip()
        for limitation in (limitations or [])
        if limitation.strip()
    ]

    if not normalized_limitations:
        raise ValueError("at least one limitation is required")

    return ModelCard(
        model_name=model_name.strip(),
        version=version.strip(),
        description=description.strip(),
        metrics={
            name: float(value)
            for name, value in metrics.items()
        },
        limitations=normalized_limitations,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def render_model_card(card: ModelCard) -> str:
    """Render a model card as Markdown."""

    metric_lines = "\n".join(
        f"- {name}: {value:.4f}"
        for name, value in sorted(card.metrics.items())
    )

    limitation_lines = "\n".join(
        f"- {item}"
        for item in card.limitations
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
