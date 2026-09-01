"""Versioned prompt loading and context serialization."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Sequence

from src.m2_rag.models import RetrievedChunk

PROMPT_DIR = Path(__file__).with_name("prompts")


def load_prompt(name: str, version: str = "v1") -> str:
    path = PROMPT_DIR / f"{name}_{version}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path.name}")
    return path.read_text(encoding="utf-8")


def render_answer_prompt(
    question: str, chunks: Sequence[RetrievedChunk], version: str = "v1"
) -> tuple[str, str]:
    system = load_prompt("system", version)
    context = "\n\n".join(
        f"[SOURCE chunk_id={chunk.chunk_id} doc_id={chunk.doc_id}]\n"
        f"Titre: {chunk.title}\nSource: {chunk.source}\nDate: {chunk.date}\n"
        f"Passage: {chunk.text}"
        for chunk in chunks
    )
    user = Template(load_prompt("answer", version)).safe_substitute(
        question=question, context=context
    )
    return system, user
