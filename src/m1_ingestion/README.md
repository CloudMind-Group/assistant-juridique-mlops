# Module 1 — Data Pipeline & Ingestion

**Owner:** Douae · **Consumer:** Module 2 (Imane — Indexation/Reranking)

Critical path: `M1 (Douae) → M2 (Imane) → M5 → M6`

## What this module does

1. Optionally generates a **synthetic sample corpus** (50–100 Moroccan legal
   documents) so M2 can start indexing without waiting for real corpus
   collection.
2. **Ingests** raw documents (`.txt` / `.pdf` / `.docx` / `.png` / `.jpg` /
   `.jpeg`) from `data/raw/`: extracts text (direct extraction for
   text-layer PDFs, OCR fallback via Tesseract for scanned PDFs and
   images), cleans it, **anonymizes PII**, and validates structured
   metadata.
3. Writes the clean, anonymized corpus to `data/processed/` in the exact
   format M2 consumes.

## Quickstart

```bash
pip install -r requirements.txt

# 1. (optional) generate a synthetic sample corpus for testing
python -m src.m1_ingestion.dataset_generator --count 60

# 2. run the ingestion pipeline (writes data/processed/ingestion_report.json)
python -m src.m1_ingestion.ingest --raw-dir data/raw --out-dir data/processed

# 3. run the data quality check (writes data/processed/quality_report.json)
python -m src.m1_ingestion.quality --processed-dir data/processed --fail-on-error

# or run both as a DVC pipeline:
dvc repro
```

OCR (scanned PDFs, `.png`/`.jpg`/`.jpeg`) requires the **Tesseract system
binary** to be installed separately (`pip install pytesseract` only
installs the Python wrapper). If it's missing, `ingest.py` logs a warning
and degrades gracefully — it does **not** crash the run — but affected
documents come out with empty/partial text and will fail `quality.py`'s
non-empty check. Install it (`fra` + `ara` language packs) if you're
ingesting scanned sources:

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

## Input layout expected in `data/raw/`

```
data/raw/
  bulletin_officiel/   <file>.txt|.pdf|.docx|.png|.jpg|.jpeg  (+ optional <file>.<ext>.meta.json)
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
| `doc_id`    | str    | unique, matches `documents/<doc_id>.txt`. Format `<source_slug>-<sha1[:16]>`, e.g. `jurisprudence-a1b2c3d4e5f60718`. **Never derived from the file name** — see PII section |
| `title`     | str    | from the sidecar when provided; otherwise `"<Source> — <date>"`, never the file name |
| `source`    | str    | `"Bulletin Officiel"` \| `"Jurisprudence"` \| `"Contrat Type"` |
| `date`      | str    | `YYYY-MM-DD` or `YYYY`                               |
| `category`  | str    | free-text legal category                             |
| `language`  | str    | `"fr"` \| `"ar"`                                     |
| `file_path` | str    | relative path to the clean text, e.g. `data/processed/documents/<doc_id>.txt` |

Additive tracking fields (optional, all default to a safe value — **do not
depend on these before syncing with Imane**, they were added after M2's
first read of this contract). Note there is deliberately no
`original_filename` field: the raw file name routinely carries a party's
name (see `ingest.make_doc_id`) and must never reach the metadata index.
Fields: `source_format`,
`extraction_method` (`"text"` \| `"pdf_direct"` \| `"ocr_pdf"` \|
`"ocr_image"` \| `"docx"`), `char_count_raw`, `word_count_raw`,
`char_count_clean`, `word_count_clean`, `anonymized` (bool), `status`
(always `"SUCCESS"` — failed documents are excluded from `metadata.jsonl`
and logged in `ingestion_report.json` instead), `processed_at` (ISO-8601
UTC timestamp).

To load the corpus in M2:

```python
import json
from pathlib import Path

records = [json.loads(line) for line in Path("data/processed/metadata.jsonl").read_text(encoding="utf-8").splitlines()]
for r in records:
    text = Path(r["file_path"]).read_text(encoding="utf-8")
    # -> chunk / embed / index `text` using `r` as metadata
```

## Collecte (connecteurs)

`collect.py` alimente `data/raw/<source_slug>/` au format attendu par
`ingest.py` (texte + sidecar `.meta.json`) :

```bash
python -m src.m1_ingestion.collect --source local --limit 50   # dépôts internes
python -m src.m1_ingestion.collect --source legifrance          # squelette, non implémenté
```

`BaseConnector` définit le contrat ; `LocalDropConnector` (dépôts internes,
lit `data/dropzone/`) est fonctionnel, `LegifranceConnector` est un
squelette qui lève `NotImplementedError` — le scraping réel demande d'abord
une revue CGU/robots.txt/quotas. Tout nouveau connecteur doit déclarer un
`source_slug` présent dans `FOLDER_TO_SOURCE` (`ingest.py`), sinon
`ingest.py` ignore silencieusement ce qu'il collecte —
`tests/m1/test_collect.py` verrouille cette correspondance.

## Dé-duplication

`ingest.py` calcule un SHA-256 du texte **nettoyé** et saute tout document
dont le contenu a déjà été ingéré dans le même run. Les doublons sont
comptés dans `IngestResult.duplicates` et listés (fichier + `duplicate_of`)
dans `ingestion_report.json`.

Le hash porte sur le texte nettoyé **avant anonymisation**, délibérément :
le masquage remplace les noms par `[NOM]`, donc deux jugements distincts
qui ne diffèrent que par les parties deviennent identiques une fois
anonymisés — dédupliquer après supprimerait un document réel en silence.

## Segmentation par articles/alinéas

`segmentation.py` détecte les frontières d'articles et d'alinéas (fr/ar) et
`ingest.py` écrit `data/processed/segments.jsonl` — un objet JSON par
segment (`doc_id`, `segment_index`, `kind`, `label`, `number`, `start`,
`end`, `text`). `metadata.jsonl` gagne aussi un champ additif
`segment_count`.

**Pour M2 :** cette sortie est *additionnelle*, `documents/` et
`metadata.jsonl` ne changent pas — le code de lecture actuel reste valide.
Elle permet de découper en respectant la structure légale plutôt qu'à
longueur fixe (un article coupé en son milieu perd son sens juridique).

La détection exige que le marqueur soit en position de titre (début de
ligne ou après une ponctuation de fin de phrase) : un renvoi comme
« conformément à l'article 41 » ou « المنصوص عليها في المادة 5 » ne crée
pas de frontière. `tests/m1/test_segmentation.py` verrouille les deux sens.

## Correction orthographique (texte océrisé uniquement)

`spelling.py` corrige le bruit d'OCR **sur les seuls documents océrisés**
(`extraction_method` valant `ocr_pdf` ou `ocr_image`). Un `.txt` ou un PDF à
texte natif n'y est jamais soumis : le corriger reviendrait à modifier un
texte qui n'avait rien de cassé.

Le correcteur ne connaît pas le français — il ne connaît qu'un **lexique
juridique fermé** (~310 termes, curé à la main). Un mot n'est corrigé que si
la correction produit un terme de ce lexique et qu'elle est **la seule** à le
faire. Deux règles :

| Règle | Exemple | S'applique à |
| --- | --- | --- |
| Restitution d'accents | `salarie` → `salarié` | mots entièrement alphabétiques |
| Confusions de caractères | `artic1e` → `article` | mots mêlant lettres et chiffres, ou portant `\|`, `!`, `$`, `@` |

C'est ce cloisonnement qui rend le correcteur inoffensif : un mot tout en
lettres ne peut être touché que par la règle des accents, donc un nom de
partie (`Benali`) ou un mot français ordinaire (`maison`) n'a aucun candidat
dans le lexique et reste intact. Un numéro de loi (`65-99`) non plus.

**Hors périmètre, assumé :** l'arabe n'est pas corrigé du tout. Les
confusions de l'OCR arabe sont d'une autre nature (formes contextuelles,
diacritiques) et aucun lexique juridique arabe n'est embarqué. Les mots
arabes sont détectés et laissés strictement intacts — mieux vaut ne rien
faire que faire semblant.

Chaque correction est tracée (`avant`, `apres`, `position`, `regle`), comme
pour l'anonymisation : une transformation du corpus qui ne laisse pas de
trace n'est pas contestable. Le décompte par règle figure dans
`ingestion_report.json` sous `ocr_corrections`.

**Étendre le lexique :** ajouter le terme dans sa forme correcte (accents
compris) à `LEXIQUE_JURIDIQUE`. Un terme dont la forme sans accent est
ambiguë avec un autre terme du lexique est automatiquement ignoré par la
règle des accents — aucune ambiguïté n'est arbitrée en silence.

## Ingestion report (pipeline-run stats)

`ingest.py` writes `data/processed/ingestion_report.json` on every run:
files discovered/processed/skipped/failed, success rate, a breakdown by
`extraction_method`, and a per-file error log. This is deliberately a
**separate file** from `quality_report.json` — that one is owned by
`quality.py` (declared output of the `quality_check` DVC stage, also read
by the Airflow DAG's `notify_m2_imane` task) and covers a different
concern: whether the resulting text/metadata is well-formed, not whether
extraction/anonymization succeeded.

## Data quality

`quality.py` re-validates `data/processed/metadata.jsonl` after ingestion:
non-empty text, required fields (`title`, `date`, `source`) present, full
`DocumentMetadata` schema/format validation, and token-length bounds
(5–20,000 whitespace tokens). It writes `data/processed/quality_report.json`
(per-document pass/fail + errors/warnings, plus a summary). Run with
`--fail-on-error` in CI/DVC/Airflow to hard-fail the pipeline on any bad
document.

## PII / RGPD (owner: Taha — M8)

**Anonymisation runs inside the pipeline, between cleaning and writing.**
Nothing in `data/processed/` — text or metadata — is expected to contain
personal data.

`anonymization_schema.py` defines the rule schema (`PIIPattern`,
`AnonymizationRuleSet`) and the default rules covering Moroccan CIN, phone
numbers, emails, names (by civility, by procedural role, and after `ENTRE`,
fr/ar) and postal addresses. `ingest.py` calls `anonymize_document()`, which
returns the masked text plus the list of spans it masked — the per-run count
is logged and surfaced in `IngestResult.pii_masked`.

Two design points worth knowing before you build on this:

- **Legal references are protected.** Docket, registry and Bulletin Officiel
  numbers share the CIN's shape, so masking them would destroy the citations
  M2 is meant to produce. Rules that anchor on a marker mask only their
  `(?P<pii>...)` group, so `"Le salarié X"` becomes `"Le salarié [NOM]"` and
  the legal fact survives. `tests/test_anonymization.py` locks this down.
- **The identifier is not derived from the file name.** A document collected
  as `arret_ahmed_benali_2024.pdf` would otherwise carry a real name into
  `doc_id` and `title`, and from there into your vector store and into the
  citations shown to end users — surviving any masking applied to the text.

`--no-anonymize` exists for local debugging only; it logs a warning and must
never be used on a real corpus.

**Name propagation.** Anchored rules need a civility or a procedural role to
fire, but a party is introduced once — "Monsieur Ahmed Benali" — then referred
to bare for pages. A second pass therefore masks every other occurrence, in the
same document, of a name an anchored rule already found. On a representative
judgment this takes name recall from 50 % to 100 %; the mechanism is seeded
only by anchored detections, so a false positive stays local instead of being
amplified across the text. Institution and procedural vocabulary is excluded
from propagation (`NON_PROPAGABLE_TOKENS`) so that `Cour`, `Tribunal` or
`salarié` are never masked document-wide.

Pass `propagate_names=False` to `anonymize_document()` to disable it — used in
the tests to demonstrate the difference, not intended for production.

**Known limit.** This remains a regex-based implementation, and propagation
seeds on anchored detections: a name that appears *only* bare, without a
civility or a role marker anywhere in the document, is still missed. Replacing
`DEFAULT_RULES` with an NER-backed detector remains the full fix and requires
no change to `ingest.py`.

> **For M2:** if a document must later be removed for a person exercising
> their right to erasure, the index has to support deleting a single
> `doc_id`. Please design for that from the start — retrofitting it means
> rebuilding the index.

**`ingest.py` now applies `anonymize_document()` to every document** before it
is written to `data/processed/documents/` — the pipeline flow is `raw file
-> extract -> clean_text -> anonymize_document -> save`. The `anonymized` field
in `metadata.jsonl` records whether a given document actually had a match
masked (`false` on the current synthetic corpus, which contains no real
PII by construction).

## Orchestration

- `dvc.yaml` (repo root) — 2-stage pipeline: `ingest` (outputs `documents/`, `metadata.jsonl`, `ingestion_report.json`) then `quality_check` (outputs `quality_report.json`), run with `dvc repro`.
- `dags/legal_ingest_v2.py` — Airflow DAG `legal_ingest_v2`, `@daily`: `run_ingestion -> run_quality_check -> notify_m2_imane`. The last task writes `data/processed/READY_FOR_M2.flag` only if the quality check passed with 0 failures.

## Files in this package

- `metadata_schema.py` — Pydantic `DocumentMetadata` model (single source of truth for the schema above).
- `ingest.py` — multi-format extraction (with OCR fallback), cleaning, anonymization, validation, and `data/processed/` export. CLI entrypoint: `python -m src.m1_ingestion.ingest`.
- `quality.py` — data quality checks + `quality_report.json`. CLI entrypoint: `python -m src.m1_ingestion.quality`.
- `anonymization_schema.py` — PII detection/masking rule schema (RGPD, with Taha), applied by `ingest.py`.
- `spelling.py` — correction orthographique adossée à un lexique juridique, appliquée par `ingest.py` au seul texte océrisé.
- `dataset_generator.py` — generates the synthetic 50–100 doc sample corpus into `data/raw/` for offline testing. Output is gitignored (`data/raw/*`), never commit generated files.

## Notes

- Raw/interim/processed data directories are gitignored except `.gitkeep` — never commit files under `data/raw/`, `data/interim/`, `data/processed/` (see root `.gitignore`).
- `dataset_generator.py` output is **synthetic placeholder legal text** for pipeline testing, not authoritative legal content.
- OCR (Tesseract) is an optional system dependency — see the Quickstart section above. Without it, scanned PDFs/images degrade to empty text (logged as a warning) instead of failing the pipeline.
