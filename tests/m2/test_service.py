from dataclasses import replace

from src.m2_rag.config import RAGConfig
from src.m2_rag.generator import FakeGroundedGenerator, GeneratedAnswer
from src.m2_rag.models import RAGRequest, RetrievedChunk
from src.m2_rag.service import KeywordScopeGuard, RAGService
from src.m2_rag.factory import build_light_service
from src.m2_rag.models import LegalDocument


def _chunk() -> RetrievedChunk:
    return RetrievedChunk("opaque-doc", "stable-chunk", "L'article impose une obligation.",
                          "Code", "Bulletin Officiel", "2024", "Civil", "fr", 0.5, "bm25+dense")


class StubRetriever:
    def __init__(self, chunks): self.chunks = chunks
    def retrieve(self, question, top_k=None, filters=None): return self.chunks[:top_k]


class HallucinatingGenerator:
    model_version = "bad-test-model"
    def generate(self, question, chunks, prompt_version):
        return GeneratedAnswer("Une règle inventée.", ["unknown-chunk"])


class UnmarkedGenerator:
    model_version = "unmarked"
    def generate(self, question, chunks, prompt_version):
        return GeneratedAnswer("Une réponse sans marqueur.", [chunks[0].chunk_id])


def test_rag_response_contains_sources_contract_and_latencies():
    service = RAGService(StubRetriever([_chunk()]), FakeGroundedGenerator())
    response = service.query(RAGRequest("Quelle obligation ?", top_k=1))
    assert not response.refused
    assert response.citations[0].doc_id == "opaque-doc"
    assert response.citations[0].chunk_id == "stable-chunk"
    assert response.prompt_version == "v1"
    assert response.model_version == "fake-grounded-v1"
    assert "retrieval_ms" in response.latencies and "total_ms" in response.latencies
    assert "conseil juridique" in response.answer


def test_refuses_without_context():
    response = RAGService(StubRetriever([]), FakeGroundedGenerator()).query("question juridique")
    assert response.refused and response.refusal_reason == "insufficient_context"
    assert not response.citations


def test_refuses_explicitly_out_of_scope():
    service = RAGService(
        StubRetriever([_chunk()]), FakeGroundedGenerator(),
        scope_guard=KeywordScopeGuard({"droit", "article", "contrat"}),
    )
    response = service.query("Donne-moi une recette de gâteau")
    assert response.refused and response.refusal_reason == "out_of_scope"


def test_rejects_citation_not_present_in_retrieved_context():
    response = RAGService(StubRetriever([_chunk()]), HallucinatingGenerator()).query("article ?")
    assert response.refused and response.refusal_reason == "ungrounded_generation"
    assert not response.citations


def test_service_works_when_tracking_is_absent():
    service = RAGService(StubRetriever([_chunk()]), FakeGroundedGenerator(), tracking_hook=None)
    assert service.query("question de droit").citations


def test_service_rejects_unmarked_answer_and_allows_french_and_arabic_legal_scope():
    assert RAGService(StubRetriever([_chunk()]), UnmarkedGenerator()).query("question de droit").refused
    guard = KeywordScopeGuard({"contrat", "قانون", "محكمة"})
    assert guard.in_scope("Quel droit régit ce contrat ?")
    assert guard.in_scope("ما هو قانون العقد؟")
    assert not guard.in_scope("Comment cuisiner un gâteau ?")
    assert not guard.in_scope("Je vais courir demain")


def test_executable_light_factory_covers_complete_m1_to_response_contract():
    document = LegalDocument(
        "doc", "Code", "BO", "2024", "Civil", "fr",
        "Article 1\nLe contrat oblige les parties à respecter leurs engagements.",
    )
    response = build_light_service([document]).query("Quelle obligation prévoit le contrat ?")
    assert not response.refused
    assert response.citations and response.retrieved_chunks
    assert response.citations[0].chunk_id in response.answer
