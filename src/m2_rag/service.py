"""Stable orchestration API consumed by M5."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

from src.m2_rag.citations import GroundingError, citation_from_chunk, validate_generated_answer
from src.m2_rag.config import RAGConfig
from src.m2_rag.corpus import validate_filter_fields
from src.m2_rag.generator import Generator
from src.m2_rag.lexical import lexical_tokens
from src.m2_rag.models import RAGRequest, RAGResponse
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
    ) -> None:
        self.retriever = retriever
        self.generator = generator
        self.config = config
        # Conservative by default: an uncertain non-legal query is refused.
        # Deployments may inject a reviewed multilingual scope classifier.
        self.scope_guard = scope_guard or KeywordScopeGuard(DEFAULT_LEGAL_TERMS)
        self.tracking_hook = tracking_hook

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

        retrieval_started = perf_counter()
        chunks = self.retriever.retrieve(
            question, top_k=request.top_k, filters=request.filters
        )
        retrieval_ms = (perf_counter() - retrieval_started) * 1000
        if not chunks:
            response = self._refusal(
                "insufficient_context", {"retrieval_ms": retrieval_ms}, chunks
            )
        else:
            generation_started = perf_counter()
            generated = self.generator.generate(question, chunks, self.config.prompt_version)
            generation_ms = (perf_counter() - generation_started) * 1000
            try:
                cited_chunks = validate_generated_answer(
                    generated.answer, generated.citation_ids, chunks
                )
            except GroundingError:
                response = self._refusal(
                    "ungrounded_generation",
                    {"retrieval_ms": retrieval_ms, "generation_ms": generation_ms},
                    chunks,
                )
            else:
                answer = generated.answer.strip()
                if DISCLAIMER.casefold() not in answer.casefold():
                    answer = f"{answer}\n\n{DISCLAIMER}"
                response = RAGResponse(
                    answer=answer,
                    citations=[citation_from_chunk(chunk) for chunk in cited_chunks],
                    retrieved_chunks=chunks,
                    prompt_version=self.config.prompt_version,
                    model_version=self.generator.model_version,
                    latencies={"retrieval_ms": retrieval_ms, "generation_ms": generation_ms},
                )
        total_ms = (perf_counter() - started) * 1000
        response.latencies["total_ms"] = total_ms
        if self.tracking_hook is not None:
            self.tracking_hook.log_query(request, response)
        return response
