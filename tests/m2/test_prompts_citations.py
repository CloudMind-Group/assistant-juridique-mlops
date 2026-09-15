import pytest

from src.m2_rag.citations import (
    GroundingError, citation_from_chunk, validate_citation_ids, validate_generated_answer,
)
from src.m2_rag.models import RetrievedChunk
from src.m2_rag.prompts import load_prompt, render_answer_prompt


def _chunk():
    return RetrievedChunk("d", "c", "x" * 600, "Titre", "Source", "2024", "Civil", "fr", 0.8, "dense")


def test_prompts_are_versioned_and_only_serialize_retrieved_sources():
    system, user = render_answer_prompt("Question", [_chunk()], "v1")
    assert "conseil juridique" in system
    assert "chunk_id=c" in user and "doc_id=d" in user


def test_citation_is_built_from_retrieved_metadata():
    citation = citation_from_chunk(_chunk(), excerpt_chars=20)
    assert citation.doc_id == "d" and citation.chunk_id == "c"
    assert len(citation.excerpt) <= 20


def test_missing_or_unknown_citations_are_rejected():
    with pytest.raises(GroundingError):
        validate_citation_ids([], [_chunk()])
    with pytest.raises(GroundingError):
        validate_citation_ids(["invented"], [_chunk()])


def test_generated_answer_requires_matching_visible_allowed_markers():
    first = _chunk()
    second = RetrievedChunk("d2", "c2", "passage", "T", "S", "2025", "Civil", "ar", 0.7, "dense")
    assert [item.chunk_id for item in validate_generated_answer(
        "Règle [chunk_id:c] et exception [chunk_id:c2].", ["c", "c2"], [first, second]
    )] == ["c", "c2"]
    for answer, ids in [
        ("Aucune citation", ["c"]),
        ("Inconnue [chunk_id:absent]", ["absent"]),
        ("Décalage [chunk_id:c2]", ["c"]),
        ("", ["c"]),
    ]:
        with pytest.raises(GroundingError):
            validate_generated_answer(answer, ids, [first, second])
