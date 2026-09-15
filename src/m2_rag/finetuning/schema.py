"""Input contract for a future PEFT LoRA/QLoRA run."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class FineTuningExample(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    context: list[str] = Field(min_length=1)
    source_doc_ids: list[str] = Field(min_length=1)
    language: str

    @field_validator("question", "answer")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @field_validator("context", "source_doc_ids")
    @classmethod
    def non_blank_list(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("list values must not be blank")
        return values

    @field_validator("language")
    @classmethod
    def supported_language(cls, value: str) -> str:
        if value not in {"fr", "ar"}:
            raise ValueError("language must be 'fr' or 'ar'")
        return value


class LoRAConfig(BaseModel):
    base_model: str
    rank: int = Field(default=16, gt=0)
    alpha: int = Field(default=32, gt=0)
    dropout: float = Field(default=0.05, ge=0, lt=1)
    target_modules: list[str] = Field(default_factory=list)
    quantization_bits: int | None = Field(default=None)
    learning_rate: float = Field(default=2e-4, gt=0)
    epochs: int = Field(default=3, gt=0)
    train_batch_size: int = Field(default=2, gt=0)
    gradient_accumulation_steps: int = Field(default=8, gt=0)

    @model_validator(mode="after")
    def validate_quantization(self):
        if self.quantization_bits not in {None, 4, 8}:
            raise ValueError("quantization_bits must be 4, 8, or omitted")
        return self

    @property
    def method(self) -> str:
        return "QLoRA" if self.quantization_bits is not None else "LoRA"
