"""RAGAS evaluation helpers for M3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RAGASEvaluationSample:
    """One RAG example ready for evaluation."""

    question: str
    answer: str
    contexts: list[str]
    reference: str | None = None

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("question must not be empty")

        if not self.answer.strip():
            raise ValueError("answer must not be empty")

        if not self.contexts:
            raise ValueError("contexts must not be empty")


def build_ragas_records(
    samples: Iterable[RAGASEvaluationSample],
) -> list[dict[str, object]]:
    """Convert M3 samples to the format consumed by RAGAS."""

    records = []

    for sample in samples:
        record = {
            "user_input": sample.question,
            "response": sample.answer,
            "retrieved_contexts": list(sample.contexts),
        }

        if sample.reference is not None:
            record["reference"] = sample.reference

        records.append(record)

    return records


def normalize_ragas_metrics(
    metrics: dict[str, object],
) -> dict[str, float]:
    """Return only numerical metrics ready to be logged in MLflow."""

    normalized: dict[str, float] = {}

    for name, value in metrics.items():
        if value is None:
            continue

        try:
            normalized[name] = float(value)
        except (TypeError, ValueError):
            continue

    return normalized
