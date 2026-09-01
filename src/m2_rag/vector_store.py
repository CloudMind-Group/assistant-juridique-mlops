"""Vector-store abstractions and Qdrant implementation."""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict
from typing import Any, Protocol, Sequence

from src.m2_rag.models import LegalChunk, RetrievedChunk


class VectorStore(Protocol):
    def upsert(self, chunks: Sequence[LegalChunk], vectors: Sequence[Sequence[float]]) -> None: ...

    def search(
        self, query_vector: Sequence[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[RetrievedChunk]: ...

    def delete_document(self, doc_id: str) -> None: ...


def _payload(chunk: LegalChunk) -> dict[str, Any]:
    # Canonical chunk fields win over additive M1 tracking metadata so an
    # accidental collision can never replace doc_id/chunk_id.
    payload = dict(chunk.metadata)
    canonical = asdict(chunk)
    canonical.pop("metadata", None)
    payload.update(canonical)
    return payload


def _retrieved(payload: dict[str, Any], score: float, method: str = "dense") -> RetrievedChunk:
    known = {
        "doc_id", "chunk_id", "text", "title", "source", "date", "category",
        "language", "chunk_index", "section"
    }
    return RetrievedChunk(
        doc_id=str(payload["doc_id"]),
        chunk_id=str(payload["chunk_id"]),
        text=str(payload["text"]),
        title=str(payload["title"]),
        source=str(payload["source"]),
        date=str(payload["date"]),
        category=str(payload["category"]),
        language=str(payload["language"]),
        score=float(score),
        retrieval_method=method,
        chunk_index=int(payload.get("chunk_index", 0)),
        section=payload.get("section"),
        metadata={key: value for key, value in payload.items() if key not in known},
    )


class InMemoryVectorStore:
    """Exact cosine store used for local/light mode and fast tests."""

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension
        self._points: dict[str, tuple[list[float], dict[str, Any]]] = {}

    def upsert(self, chunks: Sequence[LegalChunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimension:
                raise ValueError(f"expected dimension {self.dimension}, got {len(vector)}")
            self._points[chunk.chunk_id] = (list(map(float, vector)), _payload(chunk))

    def search(
        self, query_vector: Sequence[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[RetrievedChunk]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if len(query_vector) != self.dimension:
            raise ValueError(f"expected dimension {self.dimension}, got {len(query_vector)}")
        filters = filters or {}
        query_norm = math.sqrt(sum(value * value for value in query_vector)) or 1.0
        scored: list[RetrievedChunk] = []
        for vector, payload in self._points.values():
            if any(payload.get(key) != value for key, value in filters.items()):
                continue
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            score = sum(a * b for a, b in zip(query_vector, vector)) / (query_norm * norm)
            scored.append(_retrieved(payload, score))
        return sorted(scored, key=lambda item: (-item.score, item.chunk_id))[:limit]

    def delete_document(self, doc_id: str) -> None:
        doomed = [key for key, (_, payload) in self._points.items() if payload["doc_id"] == doc_id]
        for key in doomed:
            del self._points[key]


class QdrantVectorStore:
    """Qdrant collection adapter with payload-filtered document deletion."""

    def __init__(
        self,
        client: object,
        collection_name: str,
        dimension: int,
        *,
        qmodels: object | None = None,
        create_collection: bool = True,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        if qmodels is None:
            try:
                from qdrant_client import models as qmodels_imported
            except ImportError as exc:
                raise RuntimeError("qdrant-client is required for QdrantVectorStore") from exc
            qmodels = qmodels_imported
        self.client = client
        self.collection_name = collection_name
        self.dimension = dimension
        self.models = qmodels
        if create_collection:
            self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=self.models.VectorParams(
                    size=self.dimension, distance=self.models.Distance.COSINE
                ),
                hnsw_config=self.models.HnswConfigDiff(),
            )
            for field_name in ("doc_id", "source", "date", "category", "language"):
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=self.models.PayloadSchemaType.KEYWORD,
                )

    def upsert(self, chunks: Sequence[LegalChunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        points = []
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimension:
                raise ValueError(f"expected dimension {self.dimension}, got {len(vector)}")
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"m2-chunk:{chunk.chunk_id}"))
            points.append(self.models.PointStruct(id=point_id, vector=list(vector), payload=_payload(chunk)))
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def _filter(self, filters: dict[str, Any]):
        return self.models.Filter(
            must=[
                self.models.FieldCondition(key=key, match=self.models.MatchValue(value=value))
                for key, value in filters.items()
            ]
        )

    def search(
        self, query_vector: Sequence[float], limit: int, filters: dict[str, Any] | None = None
    ) -> list[RetrievedChunk]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if len(query_vector) != self.dimension:
            raise ValueError(f"expected dimension {self.dimension}, got {len(query_vector)}")
        query_filter = self._filter(filters) if filters else None
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=list(query_vector),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            points = response.points
        else:  # compatibility with older qdrant-client versions
            points = self.client.search(
                collection_name=self.collection_name,
                query_vector=list(query_vector),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        return [_retrieved(point.payload, point.score) for point in points]

    def delete_document(self, doc_id: str) -> None:
        selector = self.models.FilterSelector(filter=self._filter({"doc_id": doc_id}))
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=selector,
            wait=True,
        )
