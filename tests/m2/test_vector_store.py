from types import SimpleNamespace

import pytest

from src.m2_rag.config import HNSWConfig
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
    class Distance:
        COSINE = "Cosine"
    class VectorParams:
        def __init__(self, **kwargs): self.kwargs = kwargs
    class HnswConfigDiff:
        def __init__(self, **kwargs): self.kwargs = kwargs
    class PayloadSchemaType:
        KEYWORD = "keyword"
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


class FakeCreationClient:
    def __init__(self):
        self.created = None
        self.indexed = []
    def collection_exists(self, name): return False
    def create_collection(self, **kwargs): self.created = kwargs
    def create_payload_index(self, **kwargs): self.indexed.append(kwargs)


def test_qdrant_receives_explicit_hnsw_and_optional_jurisdiction_index():
    client = FakeCreationClient()
    hnsw = HNSWConfig(m=12, ef_construct=80, full_scan_threshold=500)
    QdrantVectorStore(client, "fixture", 3, qmodels=FakeModels, hnsw_config=hnsw)
    assert client.created["hnsw_config"].kwargs == {
        "m": 12, "ef_construct": 80, "full_scan_threshold": 500,
    }
    assert "jurisdiction" in {item["field_name"] for item in client.indexed}


def test_qdrant_delete_uses_doc_id_payload_filter_without_rebuild():
    client = FakeClient()
    store = QdrantVectorStore(client, "legal_test", 3, qmodels=FakeModels, create_collection=False)
    store.delete_document("any opaque id")
    condition = client.deleted["points_selector"].filter.must[0]
    assert condition.key == "doc_id"
    assert condition.match.value == "any opaque id"
    assert client.deleted["collection_name"] == "legal_test"


def test_real_qdrant_local_upsert_query_filters_and_targeted_delete():
    qdrant_client = pytest.importorskip("qdrant_client")
    client = qdrant_client.QdrantClient(":memory:")
    hnsw = HNSWConfig(m=12, ef_construct=80, full_scan_threshold=500)
    store = QdrantVectorStore(client, "m2_integration", 3, hnsw_config=hnsw)
    chunks = [
        _chunk("a1", "opaque-A"),
        _chunk("a2", "opaque-A"),
        _chunk("b1", "opaque-B", "ar"),
    ]
    # Exercise all real payload filter fields supported by the public contract.
    chunks[0] = LegalChunk(**{**chunks[0].__dict__, "category": "Civil", "source": "BO"})
    chunks[1] = LegalChunk(**{**chunks[1].__dict__, "category": "Social", "source": "BO"})
    chunks[2] = LegalChunk(**{**chunks[2].__dict__, "category": "Civil", "source": "Cour"})
    chunks[2] = LegalChunk(**{**chunks[2].__dict__, "date": "2025"})
    chunks[0] = LegalChunk(**{
        **chunks[0].__dict__, "metadata": {"jurisdiction": "Rabat"}
    })
    chunks[1] = LegalChunk(**{
        **chunks[1].__dict__, "metadata": {"jurisdiction": "Casablanca"}
    })
    store.upsert(chunks, [[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0]])

    assert client.collection_exists("m2_integration")
    assert [item.chunk_id for item in store.search([1, 0, 0], 5, {"doc_id": "opaque-A"})] == ["a1", "a2"]
    assert [item.chunk_id for item in store.search([1, 0, 0], 5, {"language": "ar"})] == ["b1"]
    assert [item.chunk_id for item in store.search([1, 0, 0], 5, {"category": "Social"})] == ["a2"]
    assert [item.chunk_id for item in store.search([1, 0, 0], 5, {"source": "Cour"})] == ["b1"]
    assert [item.chunk_id for item in store.search([1, 0, 0], 5, {"date": "2025"})] == ["b1"]
    # Synthetic metadata fixture only: no jurisdiction is invented for M1 data.
    assert [item.chunk_id for item in store.search(
        [1, 0, 0], 5, {"jurisdiction": "Rabat"}
    )] == ["a1"]

    store.delete_document("opaque-A")
    remaining = store.search([1, 0, 0], 5)
    assert [item.chunk_id for item in remaining] == ["b1"]
