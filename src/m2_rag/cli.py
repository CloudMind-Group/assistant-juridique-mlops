"""Small M2 CLI for validation and dependency-free local smoke runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.m2_rag.chunking import chunk_document
from src.m2_rag.config import ChunkingConfig
from src.m2_rag.corpus import load_m1_corpus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M2 RAG utilities")
    parser.add_argument("command", choices=("validate-corpus", "chunk-stats"))
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
    config = ChunkingConfig(args.chunk_size, args.chunk_overlap)
    chunks = [chunk for document in documents for chunk in chunk_document(document, config)]
    print(json.dumps({"documents": len(documents), "chunks": len(chunks), "chunking": config.version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
