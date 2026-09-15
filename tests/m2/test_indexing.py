from src.m2_rag.embeddings import DeterministicFakeEmbedder
from src.m2_rag.indexing import build_chunks, index_chunks
from src.m2_rag.models import LegalDocument
from src.m2_rag.vector_store import InMemoryVectorStore


def test_build_embed_and_upsert_pipeline_is_reproducible():
    documents = [
        LegalDocument("opaque", "Titre", "Jurisprudence", "2024", "Civil", "fr",
                      "Article 1\nUne obligation contractuelle s'applique.")
    ]
    first = build_chunks(documents)
    second = build_chunks(documents)
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    embedder = DeterministicFakeEmbedder(9)
    store = InMemoryVectorStore(embedder.dimension)
    assert index_chunks(first, embedder, store, batch_size=1) == 1
    assert store.search(embedder.embed_query("obligation contractuelle"), 1)[0].doc_id == "opaque"
