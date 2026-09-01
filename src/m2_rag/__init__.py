"""Module 2 — legal retrieval-augmented generation."""

from src.m2_rag.config import RAGConfig
from src.m2_rag.models import Citation, RAGRequest, RAGResponse, RetrievedChunk
from src.m2_rag.service import RAGService
from src.m2_rag.factory import build_light_service

__all__ = [
    "Citation",
    "RAGConfig",
    "RAGRequest",
    "RAGResponse",
    "RAGService",
    "RetrievedChunk",
    "build_light_service",
]
