"""
Module 1 — Ingestion pipeline.

Reads raw legal documents from ``data/raw/<source_slug>/`` (.txt/.pdf/.docx/
.png/.jpg/.jpeg — with OCR fallback for scanned PDFs and image-only
documents), extracts text, cleans it, **removes personal data**, attaches/
validates metadata, and writes the result to ``data/processed/`` in the
format Module 2 (Imane) consumes for indexing. See README.md in this
package for the output contract.

Pipeline flow per document:
    Raw file -> extract (direct text, or OCR fallback) -> clean_text
             -> anonymize_document -> build_metadata -> write

Anonymisation runs between cleaning and writing, so personal data never
reaches ``data/processed/`` and therefore never reaches indexing. This
placement is deliberate: once M2 has chunked and embedded a document,
removing an individual from the index is no longer a text edit but an index
rebuild. Owner of the rules: M8 (Taha) — see
:mod:`src.m1_ingestion.anonymization_schema`.

Usage:
    python -m src.m1_ingestion.ingest
    python -m src.m1_ingestion.ingest --raw-dir data/raw --out-dir data/processed
    python -m src.m1_ingestion.ingest --ocr-lang fra+ara --min-direct-text-chars 20
    python -m src.m1_ingestion.ingest --no-anonymize   # local debugging only
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.m1_ingestion.anonymization_schema import anonymize_document
from src.m1_ingestion.metadata_schema import DocumentMetadata, Language, SourceType

logger = logging.getLogger("m1_ingestion.ingest")

SUPPORTED_TEXT_EXTENSIONS = {".txt"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"} | SUPPORTED_IMAGE_EXTENSIONS

# Below this many non-whitespace chars, a PDF's direct text layer is treated
# as "effectively empty" (scanned page, or a text layer that's just a
# watermark/page number) and we fall back to OCR.
MIN_DIRECT_TEXT_CHARS = 20

# Rendering resolution for PDF-page-to-image OCR fallback. 200 DPI is a good
# tradeoff between OCR accuracy and processing time for A4 legal documents.
PDF_OCR_ZOOM = 200 / 72

# Preferred OCR language pack order — French first (majority of the M1
# corpus), Arabic second. Narrowed at runtime to whatever tessdata is
# actually installed on the host (see `_pick_ocr_languages`).
PREFERRED_OCR_LANGS = ("fra", "ara")

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
# Control/non-printable chars that sometimes leak in from OCR or malformed
# PDFs — everything in the C0/C1 ranges except \n and \t, which clean_text
# handles separately.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


@dataclass
class IngestResult:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    pii_masked: int = 0
    extraction_methods: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)


class ExtractionError(RuntimeError):
    """Raised when a raw file's text cannot be extracted."""


@dataclass
class ExtractionOutcome:
    text: str
    method: str  # "text" | "pdf_direct" | "ocr_pdf" | "ocr_image" | "docx"


# --------------------------------------------------------------------------
# OCR availability — checked once and cached, so a missing Tesseract binary
# produces exactly one warning for the whole run instead of one per file.
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception as exc:  # noqa: BLE001 - any failure means "no OCR"
        logger.warning(
            "Tesseract OCR binary not available (%s). Scanned PDFs and image "
            "documents will yield empty/partial text instead of failing the "
            "pipeline — install Tesseract to enable OCR.",
            exc,
        )
        return False


@functools.lru_cache(maxsize=1)
def _available_ocr_languages() -> frozenset[str]:
    try:
        import pytesseract

        return frozenset(pytesseract.get_languages(config=""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not list installed Tesseract languages: %s", exc)
        return frozenset()


def _pick_ocr_languages(preferred: tuple[str, ...] = PREFERRED_OCR_LANGS) -> Optional[str]:
    """Return a pytesseract `lang` string, narrowed to installed tessdata.

    Falls back fra+ara -> whichever of the two is installed -> "eng" ->
    None (meaning: don't attempt OCR, nothing usable is installed).
    """
    available = _available_ocr_languages()
    chosen = [lang for lang in preferred if lang in available]
    if chosen:
        return "+".join(chosen)
    if "eng" in available:
        logger.warning(
            "Neither 'fra' nor 'ara' Tesseract language packs are installed; "
            "falling back to 'eng' (OCR quality on French/Arabic legal text "
            "will be poor)."
        )
        return "eng"
    logger.warning("No usable Tesseract language packs installed; skipping OCR.")
    return None


def _ocr_image(image) -> str:  # image: PIL.Image.Image
    """Run Tesseract on a single in-memory image. Never raises."""
    if not _tesseract_available():
        return ""
    lang = _pick_ocr_languages()
    if lang is None:
        return ""
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang=lang)
    except Exception as exc:  # noqa: BLE001 - OCR failure degrades, doesn't crash
        logger.warning("OCR failed on an image: %s", exc)
        return ""


def _extract_pdf_direct(file_path: Path) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _extract_pdf_via_ocr(file_path: Path) -> str:
    """Rasterize each page with PyMuPDF and OCR it.

    Reuses PyMuPDF (already a dependency, already used for direct text
    extraction) to rasterize pages instead of adding pdf2image/poppler as an
    extra system dependency just to do the same job.
    """
    if not _tesseract_available():
        return ""
    import fitz  # PyMuPDF
    from PIL import Image

    pages_text: list[str] = []
    doc = fitz.open(file_path)
    try:
        matrix = fitz.Matrix(PDF_OCR_ZOOM, PDF_OCR_ZOOM)
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pages_text.append(_ocr_image(image))
    finally:
        doc.close()
    return "\n".join(pages_text)


def extract_text_from_file(file_path: Path) -> ExtractionOutcome:
    """Extract text from a .txt/.pdf/.docx/.png/.jpg/.jpeg file.

    PDFs: direct text extraction first; if the result is effectively empty
    (scanned page) and Tesseract is available, falls back to OCR. If
    Tesseract is *not* available, returns whatever direct extraction gave
    (possibly empty) with a logged warning — never raises for this reason.

    Images: OCR directly. If Tesseract is unavailable, returns an empty
    string with a logged warning instead of failing hard.
    """
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".txt":
            return ExtractionOutcome(file_path.read_text(encoding="utf-8"), method="text")

        if suffix == ".pdf":
            direct = _extract_pdf_direct(file_path)
            if len(direct.strip()) >= MIN_DIRECT_TEXT_CHARS:
                return ExtractionOutcome(direct, method="pdf_direct")
            logger.info(
                "%s: direct PDF text extraction produced %d usable chars, "
                "falling back to OCR.",
                file_path,
                len(direct.strip()),
            )
            ocr_text = _extract_pdf_via_ocr(file_path)
            if ocr_text.strip():
                return ExtractionOutcome(ocr_text, method="ocr_pdf")
            # No OCR available/successful — surface whatever direct
            # extraction produced (possibly empty) rather than failing hard.
            return ExtractionOutcome(direct, method="pdf_direct")

        if suffix == ".docx":
            import docx  # python-docx

            document = docx.Document(str(file_path))
            return ExtractionOutcome(
                "\n".join(p.text for p in document.paragraphs), method="docx"
            )

        if suffix in SUPPORTED_IMAGE_EXTENSIONS:
            from PIL import Image

            with Image.open(file_path) as image:
                text = _ocr_image(image)
            return ExtractionOutcome(text, method="ocr_image")

        raise ExtractionError(f"Unsupported extension: {suffix}")
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to caller as ExtractionError
        raise ExtractionError(f"Failed to extract text from {file_path}: {exc}") from exc


def clean_text(text: str) -> str:
    """Normalize whitespace/control noise while preserving paragraph breaks.

    - Unifies line endings.
    - Strips non-printable control characters that can leak in from OCR or
      malformed PDFs.
    - Collapses runs of spaces/tabs, and collapses 3+ blank lines down to a
      single paragraph break (one blank line) — legal article/paragraph
      structure (single blank lines between articles/alinéas) is preserved.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def detect_language(text: str) -> Language:
    return Language.AR if _ARABIC_RE.search(text) else Language.FR


def source_slug(source_file: Path, raw_dir: Path) -> str:
    """Return the source folder name, or 'document' for a file dropped in the root.

    Folder names are one of the three fixed source types, so they are safe to
    surface — unlike the file name, which is chosen by whoever collected the
    document and routinely carries a party's name.
    """
    try:
        parent = source_file.relative_to(raw_dir).parts[0]
    except (ValueError, IndexError):
        return "document"
    return parent.lower() if parent.lower() in FOLDER_TO_SOURCE else "document"


def make_doc_id(source_file: Path, raw_dir: Path) -> str:
    """Build an identifier that carries no personal data.

    The file name is deliberately excluded: an ``arret_ahmed_benali_2024.pdf``
    would otherwise put a real name into the doc_id, which propagates into the
    metadata index, into M2's vector store, and finally into the citations the
    assistant shows to end users — surviving any masking applied to the text.
    """
    # usedforsecurity=False : le condensé sert d'identifiant, pas de garantie
    # d'intégrité. Rend l'intention explicite et lève l'alerte B324 de Bandit
    # sans changer les doc_id déjà produits.
    digest = hashlib.sha1(  # noqa: S324
        str(source_file.resolve()).encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:16]
    return f"{source_slug(source_file, raw_dir)}-{digest}"


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
    source_file: Path,
    raw_dir: Path,
    out_dir: Path,
    clean_content: str,
    *,
    extraction: Optional[ExtractionOutcome] = None,
    anonymized: bool = False,
) -> DocumentMetadata:
    overrides = load_sidecar_metadata(source_file)
    doc_id = overrides.get("doc_id") or make_doc_id(source_file, raw_dir)
    source = overrides.get("source") or infer_source(source_file, raw_dir)
    if source is None:
        raise ValueError(
            f"Cannot infer 'source' for {source_file}; place it under "
            f"data/raw/{{bulletin_officiel,jurisprudence,contrats_types}}/ "
            f"or provide a {source_file.name}.meta.json sidecar."
        )
    language = overrides.get("language") or detect_language(clean_content).value
    date = str(overrides.get("date") or "1900")
    processed_path = out_dir / "documents" / f"{doc_id}.txt"

    # No title override: fall back to source + date rather than the file name,
    # which would leak a party's name into every citation (see make_doc_id).
    title = overrides.get("title") or f"{SourceType(source).value} — {date}"

    # `extraction` is optional so build_metadata keeps working as a plain
    # 4-positional-arg call (used e.g. directly in tests) without an
    # ExtractionOutcome on hand — counts then fall back to clean_content.
    raw_text = extraction.text if extraction is not None else clean_content
    extraction_method = extraction.method if extraction is not None else ""

    return DocumentMetadata(
        doc_id=doc_id,
        title=title,
        source=source,
        date=date,
        category=overrides.get("category") or "non_categorise",
        language=language,
        file_path=str(processed_path.as_posix()),
        source_format=source_file.suffix.lower(),
        extraction_method=extraction_method,
        char_count_raw=len(raw_text),
        word_count_raw=len(raw_text.split()),
        char_count_clean=len(clean_content),
        word_count_clean=len(clean_content.split()),
        anonymized=anonymized,
        status="SUCCESS",
        processed_at=datetime.now(timezone.utc).isoformat(),
    )


class IngestionPipeline:
    """Scans data/raw, extracts + cleans + anonymises text, validates
    metadata, writes output.

    `anonymise` defaults to True and should stay that way outside of local
    debugging: disabling it writes personal data into data/processed/, which
    is the exact outcome the pipeline exists to prevent.
    """

    def __init__(self, raw_dir: Path, out_dir: Path, anonymise: bool = True):
        self.raw_dir = raw_dir
        self.out_dir = out_dir
        self.anonymise = anonymise
        self.documents_dir = out_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        if not anonymise:
            logger.warning(
                "ANONYMISATION DISABLED - personal data will be written to %s. "
                "Never use this mode on a real corpus.",
                self.documents_dir,
            )

    def discover_files(self) -> list[Path]:
        if not self.raw_dir.exists():
            logger.warning("Raw directory %s does not exist.", self.raw_dir)
            return []
        return sorted(
            p
            for p in self.raw_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    def process_file(self, source_file: Path) -> tuple[DocumentMetadata, int]:
        extraction = extract_text_from_file(source_file)
        cleaned = clean_text(extraction.text)
        if not cleaned:
            raise ValueError(f"{source_file} produced empty text after cleaning")

        masked_count = 0
        if self.anonymise:
            cleaned, applied = anonymize_document(cleaned)
            masked_count = len(applied)
            if not cleaned:
                raise ValueError(f"{source_file} produced empty text after anonymisation")

        # Metadata (language, doc_id, title) is derived from the anonymised
        # text so downstream consumers never see the original.
        metadata = build_metadata(
            source_file,
            self.raw_dir,
            self.out_dir,
            cleaned,
            extraction=extraction,
            anonymized=masked_count > 0,
        )
        target = self.documents_dir / f"{metadata.doc_id}.txt"
        target.write_text(cleaned, encoding="utf-8")
        return metadata, masked_count

    def run(self) -> IngestResult:
        result = IngestResult()
        all_metadata: list[DocumentMetadata] = []

        for source_file in self.discover_files():
            try:
                metadata, masked_count = self.process_file(source_file)
            except (ExtractionError, ValueError) as exc:
                logger.error("Skipping %s: %s", source_file, exc)
                result.skipped += 1
                result.errors.append({"file": str(source_file), "error": str(exc)})
                continue
            except ValidationError as exc:
                logger.error("Metadata validation failed for %s: %s", source_file, exc)
                result.failed += 1
                result.errors.append({"file": str(source_file), "error": str(exc)})
                continue
            except Exception as exc:  # noqa: BLE001 - keep the pipeline running
                logger.exception("Unexpected error processing %s", source_file)
                result.failed += 1
                result.errors.append({"file": str(source_file), "error": str(exc)})
                continue

            all_metadata.append(metadata)
            result.processed += 1
            result.pii_masked += masked_count
            result.extraction_methods[metadata.extraction_method] = (
                result.extraction_methods.get(metadata.extraction_method, 0) + 1
            )
            logger.info(
                "Ingested %s -> %s (%s, %d PII masked)",
                source_file,
                metadata.doc_id,
                metadata.extraction_method,
                masked_count,
            )

        self._write_metadata_index(all_metadata)
        self._write_ingestion_report(result)
        logger.info(
            "Ingestion complete: %d processed, %d skipped, %d failed, %d PII masked",
            result.processed,
            result.skipped,
            result.failed,
            result.pii_masked,
        )
        return result

    def _write_metadata_index(self, all_metadata: list[DocumentMetadata]) -> None:
        index_path = self.out_dir / "metadata.jsonl"
        with index_path.open("w", encoding="utf-8") as f:
            for meta in all_metadata:
                f.write(meta.model_dump_json() + "\n")
        logger.info("Wrote metadata index: %s (%d entries)", index_path, len(all_metadata))

    def _write_ingestion_report(self, result: IngestResult) -> None:
        """Ingestion-stage summary: files processed/skipped/failed, success
        rate, PII masking count, extraction method breakdown, and per-file
        error log.

        Written to `ingestion_report.json`, deliberately *not*
        `quality_report.json` — that file is already owned by
        `quality.py` (the `quality_check` DVC stage's declared output,
        also read by the Airflow DAG's notify_m2_imane task). This report
        covers a different concern: did extraction/anonymization succeed,
        not whether the resulting text/metadata is well-formed.
        """
        total = result.processed + result.skipped + result.failed
        success_rate = round(result.processed / total, 4) if total else 0.0
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "raw_dir": str(self.raw_dir.as_posix()),
            "out_dir": str(self.out_dir.as_posix()),
            "total_files_discovered": total,
            "processed": result.processed,
            "skipped": result.skipped,
            "failed": result.failed,
            "success_rate": success_rate,
            "pii_masked": result.pii_masked,
            "extraction_methods": result.extraction_methods,
            "errors": result.errors,
        }
        report_path = self.out_dir / "ingestion_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Wrote ingestion report: %s", report_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1 legal document ingestion pipeline")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--min-direct-text-chars",
        type=int,
        default=MIN_DIRECT_TEXT_CHARS,
        help="Below this many chars, a PDF's direct text layer triggers OCR fallback.",
    )
    parser.add_argument(
        "--no-anonymize",
        action="store_true",
        help=(
            "Write the text without removing personal data. Local debugging only "
            "— never on a real corpus."
        ),
    )
    return parser.parse_args()


def main() -> IngestResult:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    global MIN_DIRECT_TEXT_CHARS
    MIN_DIRECT_TEXT_CHARS = args.min_direct_text_chars

    pipeline = IngestionPipeline(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        anonymise=not args.no_anonymize,
    )
    return pipeline.run()


if __name__ == "__main__":
    main()
