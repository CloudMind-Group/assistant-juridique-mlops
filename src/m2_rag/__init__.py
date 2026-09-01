"""Module 2 — legal retrieval-augmented generation."""

from src.m2_rag.config import RAGConfig
from src.m2_rag.models import Citation, RAGRequest, RAGResponse, RetrievedChunk
from src.m2_rag.service import RAGService

__all__ = [
    "Citation",
    "RAGConfig",
    "RAGRequest",
    "RAGResponse",
    "RAGService",
    "RetrievedChunk",
]
