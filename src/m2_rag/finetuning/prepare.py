"""Validate annotated JSONL before a future training job."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from src.m2_rag.finetuning.schema import FineTuningExample


def load_annotated_dataset(path: Path) -> list[FineTuningExample]:
    if not path.is_file():
        raise FileNotFoundError(path)
    examples: list[FineTuningExample] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            examples.append(FineTuningExample.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid fine-tuning example at line {line_number}: {exc}") from exc
    if not examples:
        raise ValueError("annotated fine-tuning dataset is empty")
    return examples
