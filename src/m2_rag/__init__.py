"""Module 2 — legal retrieval-augmented generation."""

from src.m2_rag.config import ContextCompressionConfig, HNSWConfig, QuantizationConfig, RAGConfig
from src.m2_rag.models import Citation, RAGRequest, RAGResponse, RetrievedChunk, StreamEvent
from src.m2_rag.service import RAGService
from src.m2_rag.factory import build_light_service

__all__ = [
    "Citation",
    "ContextCompressionConfig",
    "HNSWConfig",
    "QuantizationConfig",
    "RAGConfig",
    "RAGRequest",
    "RAGResponse",
    "RAGService",
    "RetrievedChunk",
    "StreamEvent",
    "build_light_service",
]
