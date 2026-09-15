"""Deterministic, structure-aware chunking for French and Arabic legal text."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from src.m2_rag.config import ChunkingConfig
from src.m2_rag.models import LegalChunk, LegalDocument

_TOKEN_RE = re.compile(r"\S+", re.UNICODE)
_HEADING_RE = re.compile(
    r"(?im)^(?P<heading>\s*(?:"
    r"article(?:\s+premier|\s+\d+[\w.-]*)?"
    r"|section(?:\s+\d+[\w.-]*)?"
    r"|chapitre(?:\s+[\w.-]+)?"
    r"|titre(?:\s+[\w.-]+)?"
    r"|المادة(?:\s+[\w\u0600-\u06ff.-]+)?"
    r"|القسم(?:\s+[\w\u0600-\u06ff.-]+)?"
    r"|الفصل(?:\s+[\w\u0600-\u06ff.-]+)?"
    r"|الباب(?:\s+[\w\u0600-\u06ff.-]+)?"
    r")\s*(?:[:—–-].*)?)$"
)


class Tokenizer(Protocol):
    def encode(self, text: str) -> list[str]: ...

    def decode(self, tokens: list[str]) -> str: ...


class WhitespaceTokenizer:
    """Small deterministic tokenizer used by default and in CI.

    Production can inject the selected embedding model tokenizer, which makes
    the 512/64 values refer to that model's actual tokens.
    """

    def encode(self, text: str) -> list[str]:
        return _TOKEN_RE.findall(text)

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)


@dataclass(frozen=True)
class _Section:
    heading: str | None
    text: str


def normalize_for_id(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.split())


def stable_chunk_id(
    *, doc_id: str, chunk_index: int, section: str | None, text: str, version: str
) -> str:
    canonical = "\x1f".join(
        [version, doc_id, str(chunk_index), normalize_for_id(section or ""), normalize_for_id(text)]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sections(text: str) -> list[_Section]:
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [_Section(None, text.strip())]
    result: list[_Section] = []
    prefix = text[: matches[0].start()].strip()
    if prefix:
        result.append(_Section(None, prefix))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append(_Section(match.group("heading").strip(), text[match.start() : end].strip()))
    return result


def chunk_document(
    document: LegalDocument,
    config: ChunkingConfig = ChunkingConfig(),
    tokenizer: Tokenizer | None = None,
) -> list[LegalChunk]:
    tokenizer = tokenizer or WhitespaceTokenizer()
    pieces: list[tuple[str | None, list[str]]] = []
    for section in _sections(document.text):
        tokens = tokenizer.encode(section.text)
        if tokens:
            pieces.append((section.heading, tokens))

    windows: list[tuple[str | None, list[str]]] = []
    current: list[str] = []
    current_section: str | None = None

    def emit() -> None:
        nonlocal current
        if current:
            windows.append((current_section, current[:]))
            current = current[-config.overlap_tokens :] if config.overlap_tokens else []

    for heading, tokens in pieces:
        offset = 0
        while offset < len(tokens):
            available = config.target_tokens - len(current)
            if available == 0:
                emit()
                available = config.target_tokens - len(current)
            take = min(available, len(tokens) - offset)
            if not current or len(current) <= config.overlap_tokens:
                current_section = heading or current_section
            current.extend(tokens[offset : offset + take])
            offset += take
            if len(current) == config.target_tokens:
                emit()
        # Prefer a semantic boundary when the accumulated chunk is already
        # substantial; short adjacent articles remain grouped efficiently.
        if current and len(current) >= config.target_tokens - config.overlap_tokens:
            emit()
    if current and (not windows or current != windows[-1][1][-len(current) :]):
        windows.append((current_section, current))

    chunks: list[LegalChunk] = []
    for index, (section, tokens) in enumerate(windows):
        text = tokenizer.decode(tokens).strip()
        chunks.append(
            LegalChunk(
                chunk_id=stable_chunk_id(
                    doc_id=document.doc_id,
                    chunk_index=index,
                    section=section,
                    text=text,
                    version=config.version,
                ),
                doc_id=document.doc_id,
                text=text,
                chunk_index=index,
                token_count=len(tokens),
                section=section,
                title=document.title,
                source=document.source,
                date=document.date,
                category=document.category,
                language=document.language,
                metadata=document.metadata,
            )
        )
    return chunks
