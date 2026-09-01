"""Injectable generation boundary; no paid API is required by M2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from src.m2_rag.models import RetrievedChunk
from src.m2_rag.prompts import render_answer_prompt


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    citation_ids: list[str]


class Generator(Protocol):
    @property
    def model_version(self) -> str: ...

    def generate(
        self, question: str, chunks: Sequence[RetrievedChunk], prompt_version: str
    ) -> GeneratedAnswer: ...


class FakeGroundedGenerator:
    """Deterministic generator for tests and offline smoke runs."""

    model_version = "fake-grounded-v1"

    def generate(
        self, question: str, chunks: Sequence[RetrievedChunk], prompt_version: str
    ) -> GeneratedAnswer:
        if not chunks:
            return GeneratedAnswer("Les sources disponibles ne permettent pas de répondre.", [])
        first = chunks[0]
        return GeneratedAnswer(
            answer=(
                f"Selon le passage récupéré, {first.text} "
                "Cette information doit être vérifiée auprès d’un professionnel du droit qualifié."
            ),
            citation_ids=[first.chunk_id],
        )


class CallableGenerator:
    """Adapter for an external/local LLM callable owned by the deployment layer."""

    def __init__(
        self,
        call: Callable[[str, str], GeneratedAnswer],
        *,
        model_version: str,
    ) -> None:
        self.call = call
        self._model_version = model_version

    @property
    def model_version(self) -> str:
        return self._model_version

    def generate(
        self, question: str, chunks: Sequence[RetrievedChunk], prompt_version: str
    ) -> GeneratedAnswer:
        system, user = render_answer_prompt(question, chunks, prompt_version)
        return self.call(system, user)
