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
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from src.m1_ingestion.anonymization_schema import anonymize_document
from src.m1_ingestion.metadata_schema import DocumentMetadata, Language, SourceType
from src.m1_ingestion.segmentation import Segment, segment_document

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
    "portails_officiels": SourceType.PORTAIL_OFFICIEL,
    "depots_internes": SourceType.DEPOT_INTERNE,
}

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
# Control/non-printable chars that sometimes leak in from OCR or malformed
# PDFs — everything in the C0/C1 ranges except \n and \t, which clean_text
# handles separately.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Lignes qui ne contiennent qu'une pagination : « Page 2 », « Page 2/4 »,
# « Page 2 sur 4 », « - 2 - », « 2/4 », « صفحة 2 ». Ancré sur la ligne
# entière (^...$ en mode MULTILINE) : une pagination citée dans une phrase
# n'est pas touchée.
_PAGE_ARTIFACT_RE = re.compile(
    r"^[ \t]*(?:"
    r"(?:page|صفحة)\s*n?[°o]?\s*\d+(?:\s*(?:/|sur|of|من)\s*\d+)?"
    r"|-+\s*\d+\s*-+"
    r"|\d+\s*/\s*\d+"
    r")[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Marqueurs structurels : jamais supprimés, même répétés. Les retirer
# casserait la segmentation par articles/alinéas.
_STRUCTURAL_MARKER_RE = re.compile(
    r"^\s*(?:Article|Alinéa|Al\.|المادة|الفقرة)\s*\d+", re.IGNORECASE
)

# Une ligne répétée au moins 3 fois et courte est un en-tête/pied de page.
MIN_HEADER_OCCURRENCES = 3
MAX_HEADER_LENGTH = 80


@dataclass
class IngestResult:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    pii_masked: int = 0
    duplicates: int = 0
    segments: int = 0
    extraction_methods: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    duplicate_files: list[dict[str, str]] = field(default_factory=list)


class ExtractionError(RuntimeError):
    """Raised when a raw file's text cannot be extracted."""


class DuplicateDocumentError(RuntimeError):
    """Raised when a file's cleaned text was already ingested in this run."""

    def __init__(self, source_file: Path, first_doc_id: str) -> None:
        super().__init__(
            f"{source_file} duplicates already-ingested document {first_doc_id}"
        )
        self.first_doc_id = first_doc_id


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

    # On lit les octets nous-mêmes et on ouvre un flux mémoire plutôt que de
    # passer le chemin à fitz : sous Windows, un fichier non-PDF laisse sinon
    # un handle ouvert après l'échec d'ouverture, et le fichier brut devient
    # impossible à déplacer ou supprimer ensuite.
    doc = fitz.open(stream=file_path.read_bytes(), filetype="pdf")
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
    doc = fitz.open(stream=file_path.read_bytes(), filetype="pdf")
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


def strip_page_artifacts(text: str) -> str:
    """Retire les lignes qui ne sont qu'un numéro de page.

    Ne traite qu'une ligne *entière* : « Page 2/4 » seul sur sa ligne part,
    « ... prévues page 2 du présent contrat » reste intact. Une pagination
    citée à l'intérieur d'une phrase fait partie du texte juridique.
    """
    return _PAGE_ARTIFACT_RE.sub("", text)


def strip_repeated_headers(
    text: str,
    *,
    min_occurrences: int = MIN_HEADER_OCCURRENCES,
    max_length: int = MAX_HEADER_LENGTH,
) -> str:
    """Retire les en-têtes/pieds de page répétés à l'identique.

    Un PDF de plusieurs pages répète le nom de la juridiction en haut de
    chaque page. Après extraction, ces répétitions se retrouvent au milieu
    du texte et polluent aussi bien la lecture que la vectorisation en aval.

    Trois garde-fous, parce qu'une suppression trop large abîmerait le fond
    juridique :

    1. **Seuls les marqueurs structurels sont protégés inconditionnellement.**
       « Article 2 » peut légitimement apparaître plusieurs fois ; le
       supprimer casserait la segmentation (voir :mod:`segmentation`).
    2. **Seules les lignes courtes** (``max_length``) sont candidates : un
       en-tête tient sur une ligne, un attendu de jugement non.
    3. **Seuil de répétition** (``min_occurrences``) : deux occurrences
       peuvent être une coïncidence, trois indiquent une structure de page.

    Alternative rejetée : supprimer toute ligne dupliquée, sans seuil ni
    borne de longueur. Plus simple, mais un contrat type qui répète deux
    fois « Fait à Casablanca » perdait les deux mentions — dont une porte
    une valeur juridique.
    """
    lines = text.split("\n")
    counts = Counter(line.strip() for line in lines if line.strip())

    repeated = {
        line
        for line, count in counts.items()
        if count >= min_occurrences
        and len(line) <= max_length
        and not _STRUCTURAL_MARKER_RE.match(line)
    }
    if not repeated:
        return text

    kept = [line for line in lines if line.strip() not in repeated]

    # Garde-fou : un document composé presque uniquement de lignes courtes
    # répétées serait entièrement effacé. Mieux vaut garder un texte avec
    # ses en-têtes qu'un document vide — quality.py rejette le vide, et la
    # perte serait alors silencieuse pour tout le reste de la chaîne.
    if not "".join(kept).strip():
        logger.warning(
            "Header stripping would empty the document; keeping it unchanged."
        )
        return text

    logger.debug("Removed %d repeated header/footer line(s)", len(lines) - len(kept))
    return "\n".join(kept)


def clean_text(text: str) -> str:
    """Normalize whitespace/control noise while preserving paragraph breaks.

    - Unifies line endings.
    - Strips non-printable control characters that can leak in from OCR or
      malformed PDFs.
    - Removes page-number lines and repeated headers/footers.
    - Collapses runs of spaces/tabs, and collapses 3+ blank lines down to a
      single paragraph break (one blank line) — legal article/paragraph
      structure (single blank lines between articles/alinéas) is preserved.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    # L'ordre compte : la normalisation des espaces d'abord, sinon deux
    # en-têtes identiques à l'espacement près ne sont pas reconnus comme
    # répétés et survivent tous les deux.
    text = strip_page_artifacts(text)
    text = strip_repeated_headers(text)
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

    Le condensé porte sur le **chemin relatif à ``raw_dir``**, normalisé en
    POSIX. Il était auparavant calculé sur ``source_file.resolve()``, donc
    sur un chemin absolu : le même document produisait un ``doc_id``
    différent sur chaque machine, et les identifiants ne se recoupaient plus
    entre le poste qui ingère et celui qui indexe.

    Alternative rejetée — hacher le *contenu* du fichier : rendrait l'ID
    stable même après déplacement, mais toute correction ultérieure du texte
    (reprise d'OCR, coquille corrigée) produirait un nouvel identifiant. M2
    verrait un document supplémentaire au lieu d'une mise à jour, et l'index
    accumulerait des doublons de versions. Le chemin relatif garde l'identité
    du document à travers les re-traitements, ce qui est la propriété utile
    ici.
    """
    try:
        relative = source_file.relative_to(raw_dir)
    except ValueError:
        # Fichier hors de raw_dir : on se rabat sur le nom seul, qui reste
        # indépendant de la machine.
        relative = Path(source_file.name)

    # as_posix() : sans cela, Windows produit « a\\b » et Linux « a/b »,
    # donc deux condensés différents pour le même document.
    # usedforsecurity=False : le condensé sert d'identifiant, pas de garantie
    # d'intégrité. Rend l'intention explicite et lève l'alerte B324 de Bandit.
    digest = hashlib.sha1(  # noqa: S324
        relative.as_posix().encode("utf-8"), usedforsecurity=False
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
    segment_count: int = 0,
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
        segment_count=segment_count,
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
        # content hash -> doc_id du premier document rencontre. Sert a la
        # deduplication : un corpus collecte depuis plusieurs sources contient
        # regulierement le meme texte deux fois (meme arret republie, meme
        # article repris dans deux bulletins).
        self._seen_hashes: dict[str, str] = {}
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

    def process_file(
        self, source_file: Path
    ) -> tuple[DocumentMetadata, int, list[Segment]]:
        extraction = extract_text_from_file(source_file)
        cleaned = clean_text(extraction.text)
        if not cleaned:
            raise ValueError(f"{source_file} produced empty text after cleaning")

        # Deduplication sur le texte *nettoye*, avant anonymisation.
        # Deliberement pas apres : le masquage remplace les noms par [NOM],
        # donc deux jugements distincts qui ne different que par les parties
        # deviennent identiques une fois anonymises. Dedupliquer apres
        # supprimerait silencieusement un document reel.
        content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        first_doc_id = self._seen_hashes.get(content_hash)
        if first_doc_id is not None:
            raise DuplicateDocumentError(source_file, first_doc_id)

        masked_count = 0
        if self.anonymise:
            cleaned, applied = anonymize_document(cleaned)
            masked_count = len(applied)
            if not cleaned:
                raise ValueError(f"{source_file} produced empty text after anonymisation")

        # Segmentation sur le texte final : les offsets stockes dans
        # segments.jsonl doivent correspondre au fichier reellement ecrit
        # dans documents/, pas a une version intermediaire.
        segments = segment_document(cleaned)

        # Metadata (language, doc_id, title) is derived from the anonymised
        # text so downstream consumers never see the original.
        metadata = build_metadata(
            source_file,
            self.raw_dir,
            self.out_dir,
            cleaned,
            extraction=extraction,
            anonymized=masked_count > 0,
            segment_count=len(segments),
        )
        target = self.documents_dir / f"{metadata.doc_id}.txt"
        target.write_text(cleaned, encoding="utf-8")

        self._seen_hashes[content_hash] = metadata.doc_id
        return metadata, masked_count, segments

    def run(self) -> IngestResult:
        result = IngestResult()
        all_metadata: list[DocumentMetadata] = []
        all_segments: list[dict[str, object]] = []

        for source_file in self.discover_files():
            try:
                metadata, masked_count, segments = self.process_file(source_file)
            except DuplicateDocumentError as exc:
                logger.info("Skipping duplicate %s: %s", source_file, exc)
                result.duplicates += 1
                result.duplicate_files.append(
                    {"file": str(source_file), "duplicate_of": exc.first_doc_id}
                )
                continue
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
            all_segments.extend(
                segment.to_dict(metadata.doc_id, index)
                for index, segment in enumerate(segments)
            )
            result.processed += 1
            result.pii_masked += masked_count
            result.segments += len(segments)
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
        self._write_segments_index(all_segments)
        self._write_ingestion_report(result)
        logger.info(
            "Ingestion complete: %d processed, %d duplicates, %d skipped, "
            "%d failed, %d PII masked, %d segments",
            result.processed,
            result.duplicates,
            result.skipped,
            result.failed,
            result.pii_masked,
            result.segments,
        )
        return result

    def _write_metadata_index(self, all_metadata: list[DocumentMetadata]) -> None:
        index_path = self.out_dir / "metadata.jsonl"
        with index_path.open("w", encoding="utf-8") as f:
            for meta in all_metadata:
                f.write(meta.model_dump_json() + "\n")
        logger.info("Wrote metadata index: %s (%d entries)", index_path, len(all_metadata))

    def _write_segments_index(self, all_segments: list[dict[str, object]]) -> None:
        """Ecrit `segments.jsonl` : un objet JSON par article/alinea detecte.

        Sortie *additionnelle* : `documents/` et `metadata.jsonl` ne changent
        pas, donc le contrat de lecture actuel de M2 reste valide tel quel.
        M2 peut s'en servir pour decouper en respectant la structure legale
        plutot qu'a longueur fixe.
        """
        index_path = self.out_dir / "segments.jsonl"
        with index_path.open("w", encoding="utf-8") as f:
            for segment in all_segments:
                f.write(json.dumps(segment, ensure_ascii=False) + "\n")
        logger.info(
            "Wrote segments index: %s (%d segments)", index_path, len(all_segments)
        )

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
        total = result.processed + result.skipped + result.failed + result.duplicates
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
            "duplicates": result.duplicates,
            "duplicate_files": result.duplicate_files,
            "segments": result.segments,
            "pii_masked": result.pii_masked,
            "extraction_methods": result.extraction_methods,
            "errors": result.errors,
        }
        # Le rapport part dans `data/processed/`, donc sur le remote partage :
        # les chemins bruts y sont substitues par une reference sans nom.
        report = redact_paths(report, self.raw_dir)

        report_path = self.out_dir / "ingestion_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Wrote ingestion report: %s", report_path)


def diagnostic_ref(source_file: Path, raw_dir: Path) -> str:
    """Reference a file in a *published* report without naming it.

    `ingestion_report.json` is written to ``data/processed/``, which is a DVC
    output pushed to the shared remote. A raw file name is chosen by whoever
    collected the document and routinely carries a party's name — the same
    reasoning that already governs `doc_id` and `title` (see `make_doc_id`).
    Applying it there and not here left the identity in a published artifact.

    The reference stays useful for diagnosis: it is deterministic, so the same
    file always yields the same reference, and the extension is kept because
    an extraction failure is usually a question of format. Whoever needs the
    real name recomputes the mapping locally against ``data/raw/`` — the one
    place where file names are allowed to exist.
    """
    return f"{make_doc_id(source_file, raw_dir)}{source_file.suffix.lower()}"


def _raw_path_pattern(raw_dir: Path) -> re.Pattern[str]:
    """Match a path pointing *inside* ``raw_dir``.

    At least one further segment is required, so ``data/raw`` on its own is
    left alone: the report legitimately states which directory it read, and a
    directory name is one of the fixed source types — safe to surface, unlike
    a file name (see `source_slug`).
    """
    return re.compile(re.escape(raw_dir.as_posix()) + r"/[^\s\"':;,]+")


def redact_paths(payload: object, raw_dir: Path) -> object:
    """Substitute every raw path in a report tree by a diagnostic reference.

    Applied when the report is serialised rather than at each recording site:
    a field added later — a duplicate list, a quarantine list — is covered
    without its author having to know this rule exists. A control that depends
    on every future contributor remembering it is a control that lapses.

    Every string is scanned, not only the values of a ``file`` key. The first
    version of this function did only the latter, and running the pipeline
    showed the name still in the report: an extraction failure carries the
    path inside its *message* (``Failed to extract text from …``). Redacting
    the field a name is expected in, and not the free text beside it, is the
    kind of half-measure that reads as a control and is not one.
    """
    motif = _raw_path_pattern(raw_dir)

    def _sur_chaine(valeur: str) -> str:
        # Les séparateurs sont uniformisés avant la recherche : le même chemin
        # s'écrit `data/raw/…` dans un champ construit par le code et
        # `data\raw\…` dans le message d'une exception levée sous Windows.
        # Chercher les deux formes dans le motif imposerait une classe de
        # caractères que la moindre erreur d'échappement rend inopérante —
        # silencieusement, ce qui est le pire mode d'échec pour un garde-fou.
        normalisee = valeur.replace("\\", "/")
        if not motif.search(normalisee):
            return valeur
        return motif.sub(
            lambda m: diagnostic_ref(Path(m.group(0)), raw_dir), normalisee
        )

    if isinstance(payload, dict):
        return {key: redact_paths(value, raw_dir) for key, value in payload.items()}
    if isinstance(payload, list):
        return [redact_paths(item, raw_dir) for item in payload]
    if isinstance(payload, str):
        return _sur_chaine(payload)
    return payload


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
