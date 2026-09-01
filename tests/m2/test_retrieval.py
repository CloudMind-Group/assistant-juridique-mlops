from src.m2_rag.embeddings import DeterministicFakeEmbedder
from src.m2_rag.lexical import BM25Index
from src.m2_rag.models import LegalChunk, RetrievedChunk
from src.m2_rag.reranker import LexicalOverlapReranker
from src.m2_rag.retrieval import DenseRetriever, HybridRetriever, ReciprocalRankFusion
from src.m2_rag.vector_store import InMemoryVectorStore


def _chunk(identifier: str, text: str, language: str = "fr") -> LegalChunk:
    return LegalChunk(identifier, f"doc-{identifier}", text, 0, len(text.split()), None,
                      "Titre", "Bulletin Officiel", "2024", "Civil", language)


def _retrieved(identifier: str, score: float, method: str) -> RetrievedChunk:
    chunk = _chunk(identifier, identifier)
    return RetrievedChunk(chunk.doc_id, identifier, chunk.text, chunk.title, chunk.source,
                          chunk.date, chunk.category, chunk.language, score, method)


def test_bm25_finds_exact_legal_reference_and_applies_filters():
    chunks = [_chunk("exact", "Application de l'article 1134 du code civil"),
              _chunk("other", "قاعدة قانونية عامة", "ar")]
    results = BM25Index(chunks).search("article 1134", 5, {"language": "fr"})
    assert [item.chunk_id for item in results] == ["exact"]


def test_rrf_uses_ranks_not_raw_score_scales():
    dense = [_retrieved("a", 0.01, "dense"), _retrieved("b", 0.009, "dense")]
    lexical = [_retrieved("b", 9000, "bm25"), _retrieved("a", 1, "bm25")]
    fused = ReciprocalRankFusion(60).fuse([(dense, 1), (lexical, 2)], 2)
    assert fused[0].chunk_id == "b"
    assert fused[0].retrieval_method == "bm25+dense"


def test_hybrid_pipeline_operates_in_light_mode_with_optional_reranker():
    chunks = [_chunk("a", "article 1134 force obligatoire du contrat"),
              _chunk("b", "règle fiscale générale")]
    embedder = DeterministicFakeEmbedder(8)
    store = InMemoryVectorStore(embedder.dimension)
    store.upsert(chunks, embedder.embed_documents([chunk.text for chunk in chunks]))
    retriever = HybridRetriever(
        BM25Index(chunks), DenseRetriever(embedder, store), ReciprocalRankFusion(),
        candidate_k=2, top_k=1, reranker=LexicalOverlapReranker(),
    )
    assert retriever.retrieve("article 1134", top_k=1)[0].chunk_id == "a"
