"""
Module 1 — Data Quality Check.

Validates the output of `src.m1_ingestion.ingest` before it is handed off
to Module 2: every document must have non-empty text, complete required
metadata (title, date, source), and metadata that matches the schema
formats/bounds. Produces a machine-readable JSON report consumed by the
Airflow DAG (`dags/legal_ingest_v2.py`) and the DVC `quality_check` stage.

Usage:
    python -m src.m1_ingestion.quality
    python -m src.m1_ingestion.quality --processed-dir data/processed
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.m1_ingestion.metadata_schema import DocumentMetadata

logger = logging.getLogger("m1_ingestion.quality")

REQUIRED_METADATA_FIELDS = ("title", "date", "source")

# Token-length sanity bounds for a single document (whitespace-split proxy
# for tokens — good enough to catch empty/truncated or absurdly bloated
# extractions without pulling in a tokenizer dependency here).
MIN_TOKENS = 5
MAX_TOKENS = 20_000


@dataclass
class DocumentCheckResult:
    doc_id: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    generated_at: str
    processed_dir: str
    total_documents: int
    passed: int
    failed: int
    pass_rate: float
    results: list[DocumentCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "processed_dir": self.processed_dir,
            "total_documents": self.total_documents,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "results": [asdict(r) for r in self.results],
        }


def _load_metadata_records(metadata_path: Path) -> list[dict[str, Any]]:
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata index not found: {metadata_path}")
    records: list[dict[str, Any]] = []
    with metadata_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.error("Malformed JSON on line %d of %s: %s", line_no, metadata_path, exc)
    return records


def check_document(record: dict[str, Any], processed_dir: Path) -> DocumentCheckResult:
    doc_id = str(record.get("doc_id", "<unknown>"))
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Required metadata fields present and non-empty.
    for required_field in REQUIRED_METADATA_FIELDS:
        value = record.get(required_field)
        if value is None or str(value).strip() == "":
            errors.append(f"missing required metadata field: '{required_field}'")

    # 2. Full schema/format validation (source enum, date pattern, language, path).
    try:
        DocumentMetadata.model_validate(record)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"schema violation on '{loc}': {err['msg']}")

    # 3. Non-vacuity + token-length bounds of the actual text file.
    file_path = record.get("file_path")
    if not file_path:
        errors.append("missing 'file_path', cannot check text content")
    else:
        text_path = Path(file_path)
        if not text_path.is_absolute():
            # file_path is stored relative to repo root; resolve against cwd.
            text_path = Path.cwd() / text_path
        if not text_path.exists():
            errors.append(f"text file not found: {file_path}")
        else:
            text = text_path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                errors.append("text file is empty")
            else:
                token_count = len(text.split())
                if token_count < MIN_TOKENS:
                    errors.append(
                        f"text too short: {token_count} tokens (min {MIN_TOKENS})"
                    )
                elif token_count > MAX_TOKENS:
                    warnings.append(
                        f"text unusually long: {token_count} tokens (max {MAX_TOKENS})"
                    )

    return DocumentCheckResult(
        doc_id=doc_id, passed=(len(errors) == 0), errors=errors, warnings=warnings
    )


def run_quality_check(processed_dir: Path) -> QualityReport:
    metadata_path = processed_dir / "metadata.jsonl"
    records = _load_metadata_records(metadata_path)

    results = [check_document(record, processed_dir) for record in records]
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    pass_rate = round(passed / len(results), 4) if results else 0.0

    report = QualityReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        processed_dir=str(processed_dir.as_posix()),
        total_documents=len(results),
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        results=results,
    )

    for r in results:
        if not r.passed:
            logger.warning("Document %s FAILED quality check: %s", r.doc_id, "; ".join(r.errors))

    logger.info(
        "Quality check complete: %d/%d passed (%.1f%%)",
        passed,
        len(results),
        pass_rate * 100,
    )
    return report


def write_report(report: QualityReport, processed_dir: Path) -> Path:
    report_path = processed_dir / "quality_report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Wrote quality report: %s", report_path)
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1 data quality check")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with code 1 if any document fails quality checks (for CI/DVC/Airflow).",
    )
    return parser.parse_args()


def main() -> QualityReport:
    args = parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    report = run_quality_check(args.processed_dir)
    write_report(report, args.processed_dir)

    if args.fail_on_error and report.failed > 0:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main()
