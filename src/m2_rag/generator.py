"""Injectable generation boundary; no paid API is required by M2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from threading import Thread
from typing import Any, Callable, Iterator, Protocol, Sequence

from src.m2_rag.config import QuantizationConfig
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


def transformers_quantization_config(config: QuantizationConfig) -> Any | None:
    """Build the standard HF config lazily; light/CPU mode has no heavy dependency."""
    if config.mode == "none":
        return None
    try:
        import bitsandbytes  # noqa: F401 - explicit optional-runtime validation
        from transformers import BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError(
            f"quantization mode '{config.mode}' requires transformers and bitsandbytes"
        ) from exc
    if config.mode == "int8":
        return BitsAndBytesConfig(load_in_8bit=True)
    return BitsAndBytesConfig(load_in_4bit=True)


def quantize_torch_cpu(model: Any, mode: str = "int8") -> Any:
    """Apply real PyTorch dynamic int8 quantization to small CPU linear models."""
    if mode != "int8":
        raise RuntimeError("PyTorch CPU dynamic quantization supports int8 here, not int4")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("torch is required for CPU dynamic int8 quantization") from exc
    return torch.ao.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)


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

    def generate_batch(self, requests):
        return [self.generate(question, chunks, version) for question, chunks, version in requests]

    def stream(self, question, chunks, prompt_version):
        generated = self.generate(question, chunks, prompt_version)
        yield from _stream_answer(generated)


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


def _stream_answer(generated: GeneratedAnswer) -> Iterator[tuple[str, Any]]:
    yield ("start", None)
    for token in generated.answer.splitlines(keepends=True):
        # Preserve exact reconstruction while keeping the fake deterministic.
        yield ("text_delta", token)
    yield ("final", generated)
    yield ("done", None)


class TransformersGenerator:
    """Lazy adapter for a configurable local Hugging Face generation pipeline."""

    def __init__(
        self,
        model_name: str,
        *,
        pipeline: Any | None = None,
        device: int | str | None = None,
        generation_kwargs: dict[str, Any] | None = None,
        quantization: QuantizationConfig = QuantizationConfig(),
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if pipeline is None:
            try:
                from transformers import pipeline as make_pipeline
            except ImportError as exc:
                raise RuntimeError("transformers is required for TransformersGenerator") from exc
            kwargs: dict[str, Any] = {"model": model_name, "task": "text-generation"}
            quantization_config = transformers_quantization_config(quantization)
            if quantization_config is not None:
                kwargs["model_kwargs"] = {"quantization_config": quantization_config}
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

    def generate_batch(self, requests):
        requests = list(requests)
        if not requests:
            return []
        prompts = []
        for question, chunks, version in requests:
            system, user = render_answer_prompt(question, chunks, version)
            prompts.append(f"{system}\n\n{user}")
        outputs = self._pipeline(prompts, **self._generation_kwargs)
        generated = []
        for prompt, output in zip(prompts, outputs):
            item = output[0] if isinstance(output, list) else output
            text = str(item["generated_text"])
            if text.startswith(prompt):
                text = text[len(prompt):].strip()
            try:
                payload = json.loads(text)
                generated.append(GeneratedAnswer(str(payload["answer"]), [str(x) for x in payload["citation_ids"]]))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError("local generator must return JSON answer/citation_ids") from exc
        return generated

    def stream(self, question, chunks, prompt_version):
        """Use the standard HF TextIteratorStreamer with the underlying model/tokenizer."""
        try:
            from transformers import TextIteratorStreamer
        except ImportError as exc:
            raise RuntimeError("transformers is required for HF streaming") from exc
        model = getattr(self._pipeline, "model", None)
        tokenizer = getattr(self._pipeline, "tokenizer", None)
        if model is None or tokenizer is None:
            # Injected lightweight pipelines remain streamable via deterministic fallback.
            yield from _stream_answer(self.generate(question, chunks, prompt_version))
            return
        system, user = render_answer_prompt(question, chunks, prompt_version)
        prompt = f"{system}\n\n{user}"
        inputs = tokenizer(prompt, return_tensors="pt")
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        errors: list[BaseException] = []
        def run() -> None:
            try:
                model.generate(**inputs, streamer=streamer, **self._generation_kwargs)
            except BaseException as exc:  # propagated in the consumer thread
                errors.append(exc)
                streamer.on_finalized_text("", stream_end=True)
        thread = Thread(target=run, daemon=True)
        thread.start()
        yield ("start", None)
        parts = []
        for delta in streamer:
            parts.append(delta)
            yield ("text_delta", delta)
        thread.join()
        if errors:
            raise RuntimeError("transformers streaming generation failed") from errors[0]
        try:
            payload = json.loads("".join(parts).strip())
            generated = GeneratedAnswer(str(payload["answer"]), [str(x) for x in payload["citation_ids"]])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError("streamed local generator must return JSON answer/citation_ids") from exc
        yield ("final", generated)
        yield ("done", None)
