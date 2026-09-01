"""Input contract for a future PEFT LoRA/QLoRA run."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FineTuningExample(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    context: list[str] = Field(min_length=1)
    source_doc_ids: list[str] = Field(min_length=1)
    language: str


class LoRAConfig(BaseModel):
    base_model: str
    rank: int = Field(default=16, gt=0)
    alpha: int = Field(default=32, gt=0)
    dropout: float = Field(default=0.05, ge=0, lt=1)
    target_modules: list[str] = Field(default_factory=list)
    quantization_bits: int | None = Field(default=None)

    @property
    def method(self) -> str:
        return "QLoRA" if self.quantization_bits is not None else "LoRA"
