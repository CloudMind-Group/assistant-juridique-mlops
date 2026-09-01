"""Validate annotated JSONL before a future training job."""

from __future__ import annotations

import argparse
import json
import random
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


def split_train_validation(
    examples: list[FineTuningExample], *, validation_ratio: float = 0.1, seed: int = 42
) -> tuple[list[FineTuningExample], list[FineTuningExample]]:
    """Return a deterministic split without writing or training anything."""
    if len(examples) < 2:
        raise ValueError("at least two examples are required for a train/validation split")
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1")
    shuffled = list(examples)
    random.Random(seed).shuffle(shuffled)
    validation_count = max(1, min(len(shuffled) - 1, round(len(shuffled) * validation_ratio)))
    return shuffled[validation_count:], shuffled[:validation_count]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a future annotated M2 QA dataset")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    examples = load_annotated_dataset(args.dataset)
    train, validation = split_train_validation(
        examples, validation_ratio=args.validation_ratio, seed=args.seed
    )
    print(json.dumps({
        "status": "valid", "examples": len(examples), "train": len(train),
        "validation": len(validation), "seed": args.seed,
        "note": "Not trained — annotated dataset validation only",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
