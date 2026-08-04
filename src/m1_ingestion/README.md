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

## Files in this package

- `metadata_schema.py` — Pydantic `DocumentMetadata` model (single source of truth for the schema above).
- `ingest.py` — extraction, cleaning, validation, and `data/processed/` export. CLI entrypoint: `python -m src.m1_ingestion.ingest`.
- `dataset_generator.py` — generates the synthetic 50–100 doc sample corpus into `data/raw/` for offline testing. Output is gitignored (`data/raw/*`), never commit generated files.

## Notes

- Raw/interim/processed data directories are gitignored except `.gitkeep` — never commit files under `data/raw/`, `data/interim/`, `data/processed/` (see root `.gitignore`).
- `dataset_generator.py` output is **synthetic placeholder legal text** for pipeline testing, not authoritative legal content.
- Legacy scripts `src/data/1_ingestion.py` and `src/data/2_ocr.py` remain for URL/OCR ingestion experiments; this package (`src/m1_ingestion/`) is the validated, metadata-complete pipeline feeding M2.
