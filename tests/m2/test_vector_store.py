from types import SimpleNamespace

from src.m2_rag.models import LegalChunk
from src.m2_rag.vector_store import InMemoryVectorStore, QdrantVectorStore


def _chunk(chunk_id: str, doc_id: str, language: str = "fr") -> LegalChunk:
    return LegalChunk(
        chunk_id, doc_id, f"texte {chunk_id}", 0, 2, "Article 1", "Titre",
        "Bulletin Officiel", "2024", "Civil", language,
    )


def test_memory_store_upsert_filters_and_delete_by_doc_id():
    store = InMemoryVectorStore(2)
    chunks = [_chunk("a1", "opaque-A"), _chunk("a2", "opaque-A"), _chunk("b1", "opaque-B", "ar")]
    store.upsert(chunks, [[1, 0], [0.9, 0.1], [0, 1]])
    assert {item.chunk_id for item in store.search([1, 0], 10, {"language": "fr"})} == {"a1", "a2"}
    store.delete_document("opaque-A")
    remaining = store.search([1, 0], 10)
    assert [item.doc_id for item in remaining] == ["opaque-B"]


class FakeModels:
    class MatchValue:
        def __init__(self, value): self.value = value
    class FieldCondition:
        def __init__(self, key, match): self.key, self.match = key, match
    class Filter:
        def __init__(self, must): self.must = must
    class FilterSelector:
        def __init__(self, filter): self.filter = filter


class FakeClient:
    def __init__(self): self.deleted = None
    def delete(self, **kwargs): self.deleted = kwargs


def test_qdrant_delete_uses_doc_id_payload_filter_without_rebuild():
    client = FakeClient()
    store = QdrantVectorStore(client, "legal_test", 3, qmodels=FakeModels, create_collection=False)
    store.delete_document("any opaque id")
    condition = client.deleted["points_selector"].filter.must[0]
    assert condition.key == "doc_id"
    assert condition.match.value == "any opaque id"
    assert client.deleted["collection_name"] == "legal_test"
