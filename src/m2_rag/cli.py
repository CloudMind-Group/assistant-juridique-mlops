"""Small M2 CLI for validation and dependency-free local smoke runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.m2_rag.chunking import chunk_document
from src.m2_rag.config import ChunkingConfig
from src.m2_rag.corpus import load_m1_corpus
from src.m2_rag.factory import build_light_service
from src.m2_rag.embeddings import DeterministicFakeEmbedder
from src.m2_rag.evaluation import benchmark_retrieval_latency
from src.m2_rag.indexing import index_chunks
from src.m2_rag.lexical import BM25Index
from src.m2_rag.retrieval import DenseRetriever, HybridRetriever, ReciprocalRankFusion
from src.m2_rag.vector_store import QdrantVectorStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M2 RAG utilities")
    parser.add_argument(
        "command",
        choices=("validate-corpus", "chunk-stats", "smoke-light", "smoke-qdrant-local"),
    )
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=64)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    documents = load_m1_corpus(args.processed_dir, repo_root=args.repo_root)
    if args.command == "validate-corpus":
        print(json.dumps({"documents": len(documents), "status": "valid"}))
        return 0
    if args.command == "smoke-light":
        service = build_light_service(documents)
        response = service.query("Quelle règle de droit est décrite dans le corpus ?")
        print(json.dumps({
            "refused": response.refused,
            "citations": len(response.citations),
            "retrieved_chunks": len(response.retrieved_chunks),
            "prompt_version": response.prompt_version,
            "model_version": response.model_version,
        }, ensure_ascii=False))
        return 0 if not response.refused and response.citations else 1
    if args.command == "smoke-qdrant-local":
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError("install requirements-m2.txt for the Qdrant smoke test") from exc
        config = ChunkingConfig(args.chunk_size, args.chunk_overlap)
        chunks = [chunk for document in documents for chunk in chunk_document(document, config)]
        embedder = DeterministicFakeEmbedder(64)
        store = QdrantVectorStore(QdrantClient(":memory:"), "m2_cli_smoke", embedder.dimension)
        index_chunks(chunks, embedder, store)
        retriever = HybridRetriever(
            BM25Index(chunks), DenseRetriever(embedder, store), ReciprocalRankFusion(),
            candidate_k=24, top_k=8,
        )
        query = lambda: retriever.retrieve("Quelle règle de droit prévoit ce document ?")
        results = query()
        report = benchmark_retrieval_latency(
            query, runs=5, backend="qdrant-local", embedder=embedder.model_version,
            corpus="M1 processed synthetic", chunk_count=len(chunks),
        )
        print(json.dumps({
            "results": len(results), "runs": report.runs, "min_ms": report.min_ms,
            "mean_ms": report.mean_ms, "p50_ms": report.p50_ms, "p95_ms": report.p95_ms,
            "backend": report.backend, "embedder": report.embedder,
            "corpus": report.corpus, "chunks": report.chunk_count,
            "environment": report.environment,
        }, ensure_ascii=False))
        return 0 if results else 1
    config = ChunkingConfig(args.chunk_size, args.chunk_overlap)
    chunks = [chunk for document in documents for chunk in chunk_document(document, config)]
    print(json.dumps({"documents": len(documents), "chunks": len(chunks), "chunking": config.version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
