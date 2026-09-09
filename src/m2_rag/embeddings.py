"""Embedding interfaces with a deterministic test implementation."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, Sequence


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def model_version(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class DeterministicFakeEmbedder:
    """Dependency-free embedder for CI; never presented as a quality model."""

    def __init__(self, dimension: int = 16, model_version: str = "fake-hash-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_version = model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_version(self) -> str:
        return self._model_version

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        for token in text.casefold().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(self.dimension):
                values[index] += (digest[index % len(digest)] / 127.5) - 1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbedder:
    """Lazy adapter for BGE-M3 or another sentence-transformers model."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        *,
        device: str = "cpu",
        normalize_embeddings: bool = True,
        model: object | None = None,
    ) -> None:
        if model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for production embeddings; "
                    "install the optional M2 model dependencies"
                ) from exc
            model = SentenceTransformer(model_name, device=device)
        self._model = model
        self._model_name = model_name
        self._normalize = normalize_embeddings
        dimension = getattr(model, "get_sentence_embedding_dimension")()
        if not dimension:
            raise ValueError("embedding model did not report a vector dimension")
        self._dimension = int(dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_version(self) -> str:
        return self._model_name

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = getattr(self._model, "encode")(
            list(texts), normalize_embeddings=self._normalize
        )
        return [list(map(float, vector)) for vector in vectors]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]
