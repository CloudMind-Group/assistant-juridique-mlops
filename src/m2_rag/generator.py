"""Injectable generation boundary; no paid API is required by M2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

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
                f"Selon le passage récupéré, {first.text} [chunk_id:{first.chunk_id}] "
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


class TransformersGenerator:
    """Lazy adapter for a configurable local Hugging Face generation pipeline."""

    def __init__(
        self,
        model_name: str,
        *,
        pipeline: Any | None = None,
        device: int | str | None = None,
        generation_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if pipeline is None:
            try:
                from transformers import pipeline as make_pipeline
            except ImportError as exc:
                raise RuntimeError("transformers is required for TransformersGenerator") from exc
            kwargs: dict[str, Any] = {"model": model_name, "task": "text-generation"}
            if device is not None:
                kwargs["device"] = device
            pipeline = make_pipeline(**kwargs)
        self._pipeline = pipeline
        self._model_version = model_name
        self._generation_kwargs = dict(generation_kwargs or {"max_new_tokens": 384})

    @property
    def model_version(self) -> str:
        return self._model_version

    def generate(
        self, question: str, chunks: Sequence[RetrievedChunk], prompt_version: str
    ) -> GeneratedAnswer:
        system, user = render_answer_prompt(question, chunks, prompt_version)
        prompt = f"{system}\n\n{user}"
        output = self._pipeline(prompt, **self._generation_kwargs)
        if not output or "generated_text" not in output[0]:
            raise ValueError("transformers pipeline returned no generated_text")
        text = str(output[0]["generated_text"])
        if text.startswith(prompt):
            text = text[len(prompt) :].strip()
        try:
            payload = json.loads(text)
            answer = str(payload["answer"])
            citation_ids = [str(item) for item in payload["citation_ids"]]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError("local generator must return JSON answer/citation_ids") from exc
        return GeneratedAnswer(answer=answer, citation_ids=citation_ids)
