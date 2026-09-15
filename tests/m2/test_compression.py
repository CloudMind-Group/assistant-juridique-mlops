
from src.m2_rag.compression import ExtractiveContextCompressor
from src.m2_rag.config import ContextCompressionConfig, RAGConfig
from src.m2_rag.generator import FakeGroundedGenerator
from src.m2_rag.models import RetrievedChunk
from src.m2_rag.service import RAGService


def _chunk(identifier: str, text: str, language: str = "fr", score: float = 1.0):
    return RetrievedChunk(
        f"doc-{identifier}", identifier, text, "Titre", "BO", "2024", "civil",
        language, score, "hybrid",
    )


class Retriever:
    def __init__(self, chunks): self.chunks = chunks
    def retrieve(self, question, top_k=None, filters=None): return list(self.chunks)


def test_context_under_budget_is_preserved_with_provenance():
    chunks = [_chunk("c1", "L'article protège le salarié."), _chunk("c2", "Le délai est fixé.")]
    result = ExtractiveContextCompressor(ContextCompressionConfig(max_tokens=20)).compress("droit", chunks)
    assert result == chunks
    assert [(c.doc_id, c.chunk_id) for c in result] == [("doc-c1", "c1"), ("doc-c2", "c2")]


def test_context_over_budget_prioritizes_rank_and_is_extractive():
    chunks = [_chunk("best", "un deux trois quatre cinq"), _chunk("later", "six sept huit")]
    result = ExtractiveContextCompressor(ContextCompressionConfig(max_tokens=4)).compress("q", chunks)
    assert [c.chunk_id for c in result] == ["best"]
    assert result[0].text == "un deux trois quatre"


def test_redundancy_and_max_chunks_are_deterministic():
    chunks = [
        _chunk("a", "Le contrat oblige les parties."),
        _chunk("b", "Le contrat oblige les parties."),
        _chunk("c", "Une règle différente existe."),
    ]
    compressor = ExtractiveContextCompressor(ContextCompressionConfig(max_tokens=50, max_chunks=2))
    first = compressor.compress("contrat", chunks)
    assert [c.chunk_id for c in first] == ["a", "c"]
    assert first == compressor.compress("contrat", chunks)


def test_french_and_arabic_source_text_is_extractively_supported():
    chunks = [_chunk("fr", "Le contrat est obligatoire.", "fr"), _chunk("ar", "العقد ملزم للأطراف.", "ar")]
    result = ExtractiveContextCompressor(ContextCompressionConfig(max_tokens=20)).compress("قانون", chunks)
    assert [c.text for c in result] == [c.text for c in chunks]
    assert [c.language for c in result] == ["fr", "ar"]


def test_compression_can_be_disabled():
    chunks = [_chunk("a", "même texte"), _chunk("b", "même texte")]
    result = ExtractiveContextCompressor(ContextCompressionConfig(enabled=False, max_tokens=1, max_chunks=1)).compress("q", chunks)
    assert result == chunks


def test_service_citations_only_reference_retained_chunks():
    chunks = [_chunk("kept", "L'article impose une obligation."), _chunk("removed", "Autre source.")]
    config = RAGConfig(compression=ContextCompressionConfig(max_tokens=5, max_chunks=1))
    response = RAGService(Retriever(chunks), FakeGroundedGenerator(), config).query("question de droit")
    assert not response.refused
    assert [c.chunk_id for c in response.retrieved_chunks] == ["kept"]
    assert [c.chunk_id for c in response.citations] == ["kept"]
