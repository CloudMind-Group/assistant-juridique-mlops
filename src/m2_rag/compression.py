"""Deterministic extractive context compression with provenance preservation."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Protocol, Sequence

from src.m2_rag.config import ContextCompressionConfig
from src.m2_rag.lexical import lexical_tokens
from src.m2_rag.models import RetrievedChunk

_TOKEN_RE = re.compile(r"\S+", re.UNICODE)
_SENTENCE_RE = re.compile(r"(?<=[.!?؟؛。])\s+|[\r\n]+", re.UNICODE)


class ContextCompressor(Protocol):
    def compress(
        self, question: str, chunks: Sequence[RetrievedChunk]
    ) -> list[RetrievedChunk]: ...


class ExtractiveContextCompressor:
    """Keep ranked source text only; never synthesize or paraphrase legal content."""

    def __init__(self, config: ContextCompressionConfig) -> None:
        self.config = config

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(_TOKEN_RE.findall(text))

    @staticmethod
    def _signature(text: str) -> set[str]:
        return set(lexical_tokens(text))

    def _redundant(self, text: str, retained: Sequence[RetrievedChunk]) -> bool:
        signature = self._signature(text)
        if not signature:
            return any(not self._signature(item.text) for item in retained)
        for item in retained:
            other = self._signature(item.text)
            union = signature | other
            similarity = len(signature & other) / len(union) if union else 1.0
            if similarity >= self.config.redundancy_threshold:
                return True
        return False

    def _extract(self, text: str, budget: int) -> str:
        if budget <= 0:
            return ""
        sentences = [part.strip() for part in _SENTENCE_RE.split(text) if part.strip()]
        kept: list[str] = []
        remaining = budget
        for sentence in sentences:
            tokens = _TOKEN_RE.findall(sentence)
            if len(tokens) <= remaining:
                kept.append(sentence)
                remaining -= len(tokens)
                continue
            if not kept:
                kept.append(" ".join(tokens[:remaining]))
            break
        return " ".join(kept).strip()

    def compress(
        self, question: str, chunks: Sequence[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        del question  # Rank is supplied by retrieval/reranking; extraction is source-only.
        if not self.config.enabled:
            return list(chunks)
        retained: list[RetrievedChunk] = []
        remaining = self.config.max_tokens
        for chunk in chunks:
            if len(retained) >= self.config.max_chunks or remaining <= 0:
                break
            if self._redundant(chunk.text, retained):
                continue
            excerpt = self._extract(chunk.text, remaining)
            used = self.count_tokens(excerpt)
            if not excerpt or used <= 0:
                continue
            retained.append(replace(chunk, text=excerpt))
            remaining -= used
        return retained
