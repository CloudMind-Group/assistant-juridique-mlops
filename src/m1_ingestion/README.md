# Module 1 — Data Pipeline & Ingestion

**Owner:** Douae · **Consumer:** Module 2 (Imane — Indexation/Reranking)

Critical path: `M1 (Douae) → M2 (Imane) → M5 → M6`

## What this module does

1. Optionally generates a **synthetic sample corpus** (50–100 Moroccan legal
   documents) so M2 can start indexing without waiting for real corpus
   collection.
2. **Ingests** raw documents (`.txt` / `.pdf` / `.docx`) from `data/raw/`,
   extracts text, cleans it, and validates structured metadata.
3. Writes the clean corpus to `data/processed/` in the exact format M2
   consumes.

## Quickstart

```bash
pip install -r requirements.txt

# 1. (optional) generate a synthetic sample corpus for testing
python -m src.m1_ingestion.dataset_generator --count 60

# 2. run the ingestion pipeline
python -m src.m1_ingestion.ingest --raw-dir data/raw --out-dir data/processed

# 3. run the data quality check (writes data/processed/quality_report.json)
python -m src.m1_ingestion.quality --processed-dir data/processed --fail-on-error

# or run both as a DVC pipeline:
dvc repro
```

## Input layout expected in `data/raw/`

```
data/raw/
  bulletin_officiel/   <file>.txt|.pdf|.docx  (+ optional <file>.<ext>.meta.json)
  jurisprudence/       ...
  contrats_types/      ...
```

The subfolder name maps to the `source` field (`Bulletin Officiel` /
`Jurisprudence` / `Contrat Type`). Drop a `<file>.<ext>.meta.json` sidecar
next to any raw file to override inferred metadata, e.g.:

```json
{
  "title": "Dahir n° 1-03-194 - Code du Travail - Article 9",
  "date": "2003-09-08",
  "category": "Droit du travail",
  "language": "fr"
}
```

## Output contract for Module 2 (read this, Imane)

```
data/processed/
  documents/<doc_id>.txt   # one clean UTF-8 text file per document
  metadata.jsonl           # one JSON object per line, one line per document
```

Each line of `metadata.jsonl` validates against
[`metadata_schema.DocumentMetadata`](metadata_schema.py):

| field       | type   | notes                                              |
|-------------|--------|-----------------------------------------------------|
| `doc_id`    | str    | unique, matches `documents/<doc_id>.txt`             |
| `title`     | str    |                                                       |
| `source`    | str    | `"Bulletin Officiel"` \| `"Jurisprudence"` \| `"Contrat Type"` |
| `date`      | str    | `YYYY-MM-DD` or `YYYY`                               |
| `category`  | str    | free-text legal category                             |
| `language`  | str    | `"fr"` \| `"ar"`                                     |
| `file_path` | str    | relative path to the clean text, e.g. `data/processed/documents/<doc_id>.txt` |

To load the corpus in M2:

```python
import json
from pathlib import Path

records = [json.loads(line) for line in Path("data/processed/metadata.jsonl").read_text(encoding="utf-8").splitlines()]
for r in records:
    text = Path(r["file_path"]).read_text(encoding="utf-8")
    # -> chunk / embed / index `text` using `r` as metadata
```

## Data quality

`quality.py` re-validates `data/processed/metadata.jsonl` after ingestion:
non-empty text, required fields (`title`, `date`, `source`) present, full
`DocumentMetadata` schema/format validation, and token-length bounds
(5–20,000 whitespace tokens). It writes `data/processed/quality_report.json`
(per-document pass/fail + errors/warnings, plus a summary). Run with
`--fail-on-error` in CI/DVC/Airflow to hard-fail the pipeline on any bad
document.

## PII / RGPD (collaboration with Taha)

`anonymization_schema.py` defines the Pydantic rule schema (`PIIPattern`,
`AnonymizationRuleSet`) used to detect and mask PII in raw legal text —
Moroccan CIN, phone numbers, emails, civility-prefixed names (fr/ar), and
postal addresses — via `detect_pii()` / `anonymize_text()`. This is a
regex-based reference implementation; Taha's team can extend `DEFAULT_RULES`
or swap in an NER-backed rule without touching the ingestion pipeline.

## Orchestration

- `dvc.yaml` (repo root) — 2-stage pipeline: `ingest` then `quality_check`, run with `dvc repro`.
- `dags/legal_ingest_v2.py` — Airflow DAG `legal_ingest_v2`, `@daily`: `run_ingestion -> run_quality_check -> notify_m2_imane`. The last task writes `data/processed/READY_FOR_M2.flag` only if the quality check passed with 0 failures.

## Files in this package

- `metadata_schema.py` — Pydantic `DocumentMetadata` model (single source of truth for the schema above).
- `ingest.py` — extraction, cleaning, validation, and `data/processed/` export. CLI entrypoint: `python -m src.m1_ingestion.ingest`.
- `quality.py` — data quality checks + `quality_report.json`. CLI entrypoint: `python -m src.m1_ingestion.quality`.
- `anonymization_schema.py` — PII detection/masking rule schema (RGPD, with Taha).
- `dataset_generator.py` — generates the synthetic 50–100 doc sample corpus into `data/raw/` for offline testing. Output is gitignored (`data/raw/*`), never commit generated files.

## Notes

- Raw/interim/processed data directories are gitignored except `.gitkeep` — never commit files under `data/raw/`, `data/interim/`, `data/processed/` (see root `.gitignore`).
- `dataset_generator.py` output is **synthetic placeholder legal text** for pipeline testing, not authoritative legal content.
- Legacy scripts `src/data/1_ingestion.py` and `src/data/2_ocr.py` remain for URL/OCR ingestion experiments; this package (`src/m1_ingestion/`) is the validated, metadata-complete pipeline feeding M2.
