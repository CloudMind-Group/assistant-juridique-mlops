"""
Module 1 — Ingestion pipeline.

Reads raw legal documents from ``data/raw/<source_slug>/``, extracts text
(.txt/.pdf/.docx), attaches/validates metadata, cleans the text, and writes
the result to ``data/processed/`` in the format Module 2 (Imane) consumes
for indexing. See README.md in this package for the output contract.

Usage:
    python -m src.m1_ingestion.ingest
    python -m src.m1_ingestion.ingest --raw-dir data/raw --out-dir data/processed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.m1_ingestion.metadata_schema import DocumentMetadata, Language, SourceType

logger = logging.getLogger("m1_ingestion.ingest")

SUPPORTED_TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}

# data/raw/<folder> -> SourceType mapping. Docs dropped directly in data/raw
# (no subfolder) fall back to a best-effort guess from the filename.
FOLDER_TO_SOURCE = {
    "bulletin_officiel": SourceType.BULLETIN_OFFICIEL,
    "jurisprudence": SourceType.JURISPRUDENCE,
    "contrats_types": SourceType.CONTRAT_TYPE,
}

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass
class IngestResult:
    processed: int = 0
    skipped: int = 0
    failed: int = 0


class ExtractionError(RuntimeError):
    """Raised when a raw file's text cannot be extracted."""


def extract_text(file_path: Path) -> str:
    """Extract raw text from a .txt/.pdf/.docx file."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".txt":
            return file_path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            try:
                return "\n".join(page.get_text("text") for page in doc)
            finally:
                doc.close()
        if suffix == ".docx":
            import docx  # python-docx

            document = docx.Document(str(file_path))
            return "\n".join(p.text for p in document.paragraphs)
        raise ExtractionError(f"Unsupported extension: {suffix}")
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to caller as ExtractionError
        raise ExtractionError(f"Failed to extract text from {file_path}: {exc}") from exc


def clean_text(text: str) -> str:
    """Light normalization: strip control noise, collapse whitespace/blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def detect_language(text: str) -> Language:
    return Language.AR if _ARABIC_RE.search(text) else Language.FR


def make_doc_id(source_file: Path) -> str:
    digest = hashlib.sha1(str(source_file.resolve()).encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", source_file.stem).strip("-").lower()[:40]
    return f"{slug}-{digest}"


def load_sidecar_metadata(source_file: Path) -> dict:
    """Optional ``<file>.meta.json`` next to the raw file overrides inferred fields."""
    sidecar = source_file.with_suffix(source_file.suffix + ".meta.json")
    if not sidecar.exists():
        return {}
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Ignoring invalid sidecar metadata %s: %s", sidecar, exc)
        return {}


def infer_source(source_file: Path, raw_dir: Path) -> Optional[SourceType]:
    try:
        rel_parent = source_file.relative_to(raw_dir).parts[0]
    except (ValueError, IndexError):
        return None
    return FOLDER_TO_SOURCE.get(rel_parent.lower())


def build_metadata(
    source_file: Path, raw_dir: Path, out_dir: Path, clean_content: str
) -> DocumentMetadata:
    overrides = load_sidecar_metadata(source_file)
    doc_id = overrides.get("doc_id") or make_doc_id(source_file)
    source = overrides.get("source") or infer_source(source_file, raw_dir)
    if source is None:
        raise ValueError(
            f"Cannot infer 'source' for {source_file}; place it under "
            f"data/raw/{{bulletin_officiel,jurisprudence,contrats_types}}/ "
            f"or provide a {source_file.name}.meta.json sidecar."
        )
    language = overrides.get("language") or detect_language(clean_content).value
    processed_path = out_dir / "documents" / f"{doc_id}.txt"

    return DocumentMetadata(
        doc_id=doc_id,
        title=overrides.get("title") or source_file.stem.replace("_", " ").title(),
        source=source,
        date=str(overrides.get("date") or "1900"),
        category=overrides.get("category") or "non_categorise",
        language=language,
        file_path=str(processed_path.as_posix()),
    )


class IngestionPipeline:
    """Scans data/raw, extracts + cleans text, validates metadata, writes output."""

    def __init__(self, raw_dir: Path, out_dir: Path):
        self.raw_dir = raw_dir
        self.out_dir = out_dir
        self.documents_dir = out_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def discover_files(self) -> list[Path]:
        if not self.raw_dir.exists():
            logger.warning("Raw directory %s does not exist.", self.raw_dir)
            return []
        return sorted(
            p
            for p in self.raw_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    def process_file(self, source_file: Path) -> Optional[DocumentMetadata]:
        raw_text = extract_text(source_file)
        cleaned = clean_text(raw_text)
        if not cleaned:
            raise ValueError(f"{source_file} produced empty text after cleaning")

        metadata = build_metadata(source_file, self.raw_dir, self.out_dir, cleaned)
        target = self.documents_dir / f"{metadata.doc_id}.txt"
        target.write_text(cleaned, encoding="utf-8")
        return metadata

    def run(self) -> IngestResult:
        result = IngestResult()
        all_metadata: list[DocumentMetadata] = []

        for source_file in self.discover_files():
            try:
                metadata = self.process_file(source_file)
            except (ExtractionError, ValueError) as exc:
                logger.error("Skipping %s: %s", source_file, exc)
                result.skipped += 1
                continue
            except ValidationError as exc:
                logger.error("Metadata validation failed for %s: %s", source_file, exc)
                result.failed += 1
                continue
            except Exception:  # noqa: BLE001 - keep the pipeline running
                logger.exception("Unexpected error processing %s", source_file)
                result.failed += 1
                continue

            all_metadata.append(metadata)
            result.processed += 1
            logger.info("Ingested %s -> %s", source_file, metadata.doc_id)

        self._write_metadata_index(all_metadata)
        logger.info(
            "Ingestion complete: %d processed, %d skipped, %d failed",
            result.processed,
            result.skipped,
            result.failed,
        )
        return result

    def _write_metadata_index(self, all_metadata: list[DocumentMetadata]) -> None:
        index_path = self.out_dir / "metadata.jsonl"
        with index_path.open("w", encoding="utf-8") as f:
            for meta in all_metadata:
                f.write(meta.model_dump_json() + "\n")
        logger.info("Wrote metadata index: %s (%d entries)", index_path, len(all_metadata))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1 legal document ingestion pipeline")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> IngestResult:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pipeline = IngestionPipeline(raw_dir=args.raw_dir, out_dir=args.out_dir)
    return pipeline.run()


if __name__ == "__main__":
    main()
