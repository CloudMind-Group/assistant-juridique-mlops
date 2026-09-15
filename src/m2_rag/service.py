"""Stable orchestration API consumed by M5."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Iterator, Protocol, Sequence

from src.m2_rag.citations import GroundingError, citation_from_chunk, validate_generated_answer
from src.m2_rag.config import RAGConfig
from src.m2_rag.compression import ContextCompressor, ExtractiveContextCompressor
from src.m2_rag.corpus import validate_filter_fields
from src.m2_rag.generator import GeneratedAnswer, Generator
from src.m2_rag.lexical import lexical_tokens
from src.m2_rag.models import RAGRequest, RAGResponse, RetrievedChunk, StreamEvent
from src.m2_rag.retrieval import HybridRetriever

DISCLAIMER = (
    "Cet assistant ne délivre pas de conseil juridique. Les références doivent être "
    "vérifiées avant toute décision auprès d’un professionnel du droit qualifié."
)


class ScopeGuard(Protocol):
    def in_scope(self, question: str) -> bool: ...


class KeywordScopeGuard:
    """Replaceable multilingual keyword baseline; it is not a classifier."""

    def __init__(self, legal_terms: set[str]) -> None:
        self.legal_terms = {term.casefold().strip() for term in legal_terms if term.strip()}

    def in_scope(self, question: str) -> bool:
        folded = question.casefold()
        tokens = set(lexical_tokens(question))
        return any(term in tokens or (" " in term and term in folded) for term in self.legal_terms)


DEFAULT_LEGAL_TERMS = {
    "droit", "juridique", "loi", "article", "contrat", "tribunal", "cour",
    "jugement", "arrêt", "dahir", "code", "obligation", "salarié", "employeur",
    "المادة", "قانون", "عقد", "محكمة", "حكم", "قانوني",
}


class RAGService:
    def __init__(
        self,
        retriever: HybridRetriever,
        generator: Generator,
        config: RAGConfig = RAGConfig(),
        *,
        scope_guard: ScopeGuard | None = None,
        tracking_hook: Any | None = None,
        context_compressor: ContextCompressor | None = None,
    ) -> None:
        self.retriever = retriever
        self.generator = generator
        self.config = config
        # Conservative by default: an uncertain non-legal query is refused.
        # Deployments may inject a reviewed multilingual scope classifier.
        self.scope_guard = scope_guard or KeywordScopeGuard(DEFAULT_LEGAL_TERMS)
        self.tracking_hook = tracking_hook
        self.context_compressor = context_compressor or ExtractiveContextCompressor(
            config.compression
        )

    def _refusal(
        self, reason: str, latencies: dict[str, float], retrieved_chunks=None
    ) -> RAGResponse:
        return RAGResponse(
            answer=f"Je ne peux pas répondre à partir du corpus juridique disponible. {DISCLAIMER}",
            citations=[],
            retrieved_chunks=list(retrieved_chunks or []),
            prompt_version=self.config.prompt_version,
            model_version=self.generator.model_version,
            latencies=latencies,
            refused=True,
            refusal_reason=reason,
        )

    def _finalize_generated(
        self,
        generated: GeneratedAnswer,
        chunks: list[RetrievedChunk],
        latencies: dict[str, float],
    ) -> RAGResponse:
        try:
            cited_chunks = validate_generated_answer(
                generated.answer, generated.citation_ids, chunks
            )
        except GroundingError:
            return self._refusal("ungrounded_generation", latencies, chunks)
        answer = generated.answer.strip()
        if DISCLAIMER.casefold() not in answer.casefold():
            answer = f"{answer}\n\n{DISCLAIMER}"
        return RAGResponse(
            answer=answer,
            citations=[citation_from_chunk(chunk) for chunk in cited_chunks],
            retrieved_chunks=chunks,
            prompt_version=self.config.prompt_version,
            model_version=self.generator.model_version,
            latencies=latencies,
        )

    def _retrieve(self, request: RAGRequest) -> tuple[list[RetrievedChunk], float]:
        started = perf_counter()
        chunks = self.retriever.retrieve(
            request.question.strip(), top_k=request.top_k, filters=request.filters
        )
        elapsed = (perf_counter() - started) * 1000
        return self.context_compressor.compress(request.question.strip(), chunks), elapsed

    def query(self, request: RAGRequest | str) -> RAGResponse:
        if isinstance(request, str):
            request = RAGRequest(question=request)
        question = request.question.strip()
        if not question:
            return self._refusal("empty_question", {"total_ms": 0.0})
        validate_filter_fields(request.filters)
        started = perf_counter()
        if not self.scope_guard.in_scope(question):
            elapsed = (perf_counter() - started) * 1000
            return self._refusal("out_of_scope", {"total_ms": elapsed})

        chunks, retrieval_ms = self._retrieve(request)
        if not chunks:
            response = self._refusal(
                "insufficient_context", {"retrieval_ms": retrieval_ms}, chunks
            )
        else:
            generation_started = perf_counter()
            generated = self.generator.generate(question, chunks, self.config.prompt_version)
            generation_ms = (perf_counter() - generation_started) * 1000
            response = self._finalize_generated(
                generated, chunks,
                {"retrieval_ms": retrieval_ms, "generation_ms": generation_ms},
            )
        total_ms = (perf_counter() - started) * 1000
        response.latencies["total_ms"] = total_ms
        if self.tracking_hook is not None:
            self.tracking_hook.log_query(request, response)
        return response

    def query_batch(
        self, requests: Sequence[RAGRequest | str], *, batch_size: int = 8
    ) -> list[RAGResponse]:
        """Return independent ordered responses, using native generation batches when available."""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        normalized = [item if isinstance(item, RAGRequest) else RAGRequest(item) for item in requests]
        responses: list[RAGResponse | None] = [None] * len(normalized)
        native = getattr(self.generator, "generate_batch", None)
        if not callable(native):
            return [self.query(item) for item in normalized]
        for offset in range(0, len(normalized), batch_size):
            pending = []
            for index in range(offset, min(offset + batch_size, len(normalized))):
                request = normalized[index]
                question = request.question.strip()
                started = perf_counter()
                if not question:
                    responses[index] = self._refusal("empty_question", {"total_ms": 0.0})
                    continue
                validate_filter_fields(request.filters)
                if not self.scope_guard.in_scope(question):
                    responses[index] = self._refusal(
                        "out_of_scope", {"total_ms": (perf_counter() - started) * 1000}
                    )
                    continue
                chunks, retrieval_ms = self._retrieve(request)
                if not chunks:
                    responses[index] = self._refusal(
                        "insufficient_context", {"retrieval_ms": retrieval_ms}, chunks
                    )
                    continue
                pending.append((index, request, chunks, retrieval_ms, started))
            if pending:
                generation_started = perf_counter()
                generated_batch = native([
                    (item.question.strip(), chunks, self.config.prompt_version)
                    for _, item, chunks, _, _ in pending
                ])
                generation_ms = (perf_counter() - generation_started) * 1000
                if len(generated_batch) != len(pending):
                    raise ValueError("generator batch result count does not match request count")
                for (index, request, chunks, retrieval_ms, started), generated in zip(pending, generated_batch):
                    response = self._finalize_generated(
                        generated, chunks,
                        {"retrieval_ms": retrieval_ms, "generation_ms": generation_ms},
                    )
                    response.latencies["total_ms"] = (perf_counter() - started) * 1000
                    if self.tracking_hook is not None:
                        self.tracking_hook.log_query(request, response)
                    responses[index] = response
        return [response for response in responses if response is not None]

    def stream_query(self, request: RAGRequest | str) -> Iterator[StreamEvent]:
        """Stream M2 events without imposing an HTTP/SSE transport on M5."""
        if isinstance(request, str):
            request = RAGRequest(request)
        question = request.question.strip()
        yield StreamEvent("start")
        if not question or not self.scope_guard.in_scope(question):
            reason = "empty_question" if not question else "out_of_scope"
            response = self._refusal(reason, {"total_ms": 0.0})
            yield StreamEvent("refusal", response=response)
            yield StreamEvent("done", response=response)
            return
        validate_filter_fields(request.filters)
        started = perf_counter()
        chunks, retrieval_ms = self._retrieve(request)
        if not chunks:
            response = self._refusal("insufficient_context", {"retrieval_ms": retrieval_ms}, chunks)
            yield StreamEvent("refusal", response=response)
            yield StreamEvent("done", response=response)
            return
        stream = getattr(self.generator, "stream", None)
        try:
            if callable(stream):
                generated = None
                for event, payload in stream(question, chunks, self.config.prompt_version):
                    if event == "text_delta":
                        yield StreamEvent("text_delta", text_delta=str(payload))
                    elif event == "final":
                        generated = payload
            else:
                generated = self.generator.generate(question, chunks, self.config.prompt_version)
                yield StreamEvent("text_delta", text_delta=generated.answer)
            if generated is None:
                raise ValueError("generator stream did not provide a final answer")
            response = self._finalize_generated(
                generated, chunks, {"retrieval_ms": retrieval_ms}
            )
            response.latencies["total_ms"] = (perf_counter() - started) * 1000
            event_name = "refusal" if response.refused else "final"
            yield StreamEvent(event_name, response=response)
            yield StreamEvent("done", response=response)
        except Exception as exc:
            yield StreamEvent("error", error=str(exc))
            yield StreamEvent("done")
