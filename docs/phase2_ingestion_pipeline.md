# Phase 2: Ingestion Pipeline

This document covers the full document ingestion system built in Phase 2 of the Animal Welfare Compliance Intelligence Platform — from file upload through OCR, cleaning, classification, metadata extraction, categorization, and retrieval summary generation.

---

## Overview

Phase 2 transforms raw USDA/APHIS documents (PDFs, DOCX files, plain text) into structured, searchable records in the database. Every document passes through a five-stage Celery pipeline that runs asynchronously in the background after upload.

```
File Upload (API or bulk ingest script)
  └─→ Supabase Storage                        [file stored]
  └─→ documents row created (status: pending)
        └─→ task_ocr_extract                  [text extracted]
              └─→ task_clean                  [text normalized]
                    └─→ task_classify         [doc_type confirmed]
                          └─→ task_enrich     [metadata, categories, retrieval summary]
                                              [status: complete]
```

Each task is independently retryable (max 2 retries). Failures write the stage name and error to `documents.error_message` (e.g. `"ocr_extract: file download failed"`) and set `status = "failed"`.

---

## Pre-Phase-2 Migration

Before Phase 2 code could run, the Phase 1 database schema was aligned to the authoritative spec via the Alembic migration `c3d4e5f6a7b8_phase1_schema_fix`:

- Created the `users` table (id, email, hashed_password, full_name, role, is_active, last_login_at)
- Renamed `documents.uploaded_by` → `documents.ingested_by` with FK to `users(id) ON DELETE SET NULL`
- Added `documents.source` column
- Fixed `document_metadata.inspection_date` from `DateTime` → `Date`
- Added 9 missing indexes: `idx_documents_status`, `idx_documents_doc_type`, `idx_documents_source`, `idx_document_metadata_document_id`, `idx_document_metadata_jurisdiction`, GIN indexes on `species` and `categories`

Run migrations: `docker compose exec api alembic upgrade head`

---

## LLM Configuration

All LLM calls use OpenRouter as an OpenAI-compatible proxy. The client is constructed once in `backend/app/llm.py`:

```python
def get_llm_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,   # https://openrouter.ai/api/v1
    )
```

| Setting | Value |
|---|---|
| `openrouter_api_key` | Set in `.env` as `OPENROUTER_API_KEY` |
| `openrouter_base_url` | `https://openrouter.ai/api/v1` |
| `llm_mini_model` | `openai/gpt-4o-mini` — used for all pipeline stages |
| `llm_chat_model` | `openai/gpt-4o` — reserved for Phase 6 grounded chat |

Every pipeline LLM call uses `gpt-4o-mini` with `temperature=0` (or 0.1 for the summarizer) and a tight `max_tokens` budget to minimize cost.

---

## Upload Entry Points

### API Upload (superadmin only)

`POST /api/ingest` — multipart form upload:

```
file:      <binary>
doc_type:  inspection_report | regulation | policy | enforcement_action
source:    USDA_APHIS | CFR_Title9 | APHIS_Enforcement | APHIS_Policy
```

The route validates `doc_type` and `source`, uploads the file to Supabase Storage at path `{doc_type}/{uuid}/{original_filename}`, creates the `documents` row, and calls `run_ingestion_pipeline(document_id)`.

Source: `backend/app/api/routes/ingest.py`

### Bulk Ingest Script

`backend/scripts/bulk_ingest.py` — reads from the local `corpus/` directory (mounted read-only into the container at `/app/corpus`) and ingests all files.

**Directory mapping:**

| Subdirectory | doc_type | source |
|---|---|---|
| `corpus/inspection_reports/` | `inspection_report` | `USDA_APHIS` |
| `corpus/enforcement_actions/` | `enforcement_action` | `APHIS_Enforcement` |
| `corpus/regulations/` | `regulation` | `CFR_Title9` |
| `corpus/policies/` | `policy` | `APHIS_Policy` |

**Usage (run inside the api container):**

```bash
# Test with 5 files
docker compose exec api python scripts/bulk_ingest.py --limit 5

# Dry run — shows what would be ingested without making changes
docker compose exec api python scripts/bulk_ingest.py --dry-run

# Full corpus ingest (background)
docker compose exec -d api python scripts/bulk_ingest.py

# Single doc type only
docker compose exec api python scripts/bulk_ingest.py --doc-type inspection_report

# Skip Supabase upload — use local file path (dev only)
docker compose exec api python scripts/bulk_ingest.py --skip-upload --limit 10
```

The script checks `documents.original_name` uniqueness before uploading — already-ingested files are skipped automatically.

---

## Pipeline Stages

### Stage 1 — `task_ocr_extract`

**File:** `backend/app/ingestion/ocr.py`  
**Celery task:** `tasks.ocr_extract` | max_retries=2, retry_delay=15s

Downloads the file from Supabase Storage and extracts raw text. Routing by MIME type:

| MIME type | Handler |
|---|---|
| `application/pdf` | PyMuPDF native extraction, falls back to Tesseract if < 100 chars extracted |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx paragraph join |
| `text/plain` | UTF-8 decode |

**Scanned PDF fallback:** If PyMuPDF extracts fewer than 100 characters from a PDF, the document is treated as a scanned image. Each page is rasterized at 2× scale (via `fitz.Matrix(2, 2)`) to improve OCR accuracy, then passed through Tesseract (`tesseract-ocr-eng`).

Output written to: `documents.raw_text`

---

### Stage 2 — `task_clean`

**File:** `backend/app/ingestion/cleaner.py`  
**Celery task:** `tasks.clean` | max_retries=2, retry_delay=15s

Normalizes the raw extracted text to reduce noise before LLM processing:

| Operation | What it fixes |
|---|---|
| Line ending normalization | `\r\n` and `\r` → `\n` |
| OCR hyphenation repair | `word-\nnext` → `wordnext` |
| Whitespace collapse | Multiple spaces/tabs → single space |
| Blank line collapse | More than 2 consecutive blank lines → 2 |
| Control character strip | Removes `\x00–\x08`, `\x0b–\x1f`, `\x7f` |

Output overwrites `documents.raw_text`.

---

### Stage 3 — `task_classify`

**File:** `backend/app/ingestion/classifier.py`  
**Celery task:** `tasks.classify` | max_retries=2, retry_delay=15s  
**LLM:** `gpt-4o-mini`, max_tokens=20, temperature=0

Confirms or corrects the `doc_type` set at upload time. The prompt shows the first 1,500 characters of text and provides a "hint" (the pre-assigned `doc_type`) as a strong prior that is only overridden if clearly wrong.

Document type signals the classifier uses:

| Type | Corpus signals |
|---|---|
| `inspection_report` | "Inspection Report" header, certificate number (e.g. `93-C-0119`), CFR violation citations (e.g. `2.126(b) REPEAT`), "Prepared By" inspector line, "Species Inspected" table |
| `enforcement_action` | "BEFORE THE SECRETARY OF AGRICULTURE", "AWA Docket No.", "CONSENT DECISION AND ORDER", civil penalty amount |
| `regulation` | Legal regulatory text: Animal Welfare Act statutes or 9 CFR Title 9 |
| `policy` | APHIS operational policy, inspection guide, procedure manual |

If the LLM returns an unknown value or fails, the original hint is kept unchanged. Any correction is logged at INFO level.

Output written to: `documents.doc_type`

---

### Stage 4 — `task_enrich`

**File:** `backend/app/ingestion/metadata_extractor.py`, `categorizer.py`, `summarizer.py`  
**Celery task:** `tasks.enrich` | max_retries=2, retry_delay=30s  
**LLM:** `gpt-4o-mini` for all three sub-calls

The enrich stage runs three LLM calls and writes their results before setting `status = "complete"`.

#### 4a. Metadata Extraction

Extracts structured fields from the first 3,000 characters using JSON-mode output:

| Field | Description |
|---|---|
| `issuer` | Always "USDA APHIS" for this corpus |
| `jurisdiction` | Two-letter US state code from facility or respondent address |
| `facility_name` | Licensed facility name, licensee name, or respondent entity |
| `species` | Array of common species names mentioned in the document |
| `inspection_date` | Inspection date (reports) or decision date (enforcement actions), as `DATE` |
| `inspector_name` | Full name from the "Prepared By" field |
| `reference_number` | AWA certificate number (e.g. `93-C-0119`) or AWA Docket No. |

Date parsing handles multiple formats from the corpus: `YYYY-MM-DD`, `DD-Mon-YYYY` (e.g. `20-FEB-2015`), `MM/DD/YYYY`, `Month DD, YYYY`.

Null/None/N/A strings are normalized to Python `None`. Results are upserted into the `document_metadata` table.

#### 4b. Categorization

Classifies the document into applicable violation/issue categories from the first 3,000 characters. Returns a JSON array filtered to valid values only.

Valid categories and their regulatory anchors:

| Category | CFR basis |
|---|---|
| `overcrowding` | 9 CFR §3.x housing space requirements |
| `veterinary_care` | 9 CFR §2.40 attending veterinarian program |
| `transport_conditions` | 9 CFR §3.x transport standards |
| `sanitation` | 9 CFR §3.11, §3.31, §3.131 |
| `water_access` | 9 CFR §3.9, §3.29, §3.129 |
| `euthanasia` | 9 CFR §2.x euthanasia methods |
| `housing` | 9 CFR §3.x housing facilities, shelter, temperature |
| `feeding` | 9 CFR §3.9, §3.29 food supply |
| `handling` | 9 CFR §2.131 handling, public contact |
| `recordkeeping` | 9 CFR §2.75, §2.126 recordkeeping and access |

Written to: `document_metadata.categories` (TEXT[] column with GIN index)

#### 4c. Retrieval Summary Generation

Generates a keyword-dense, normalized-terminology artifact from the first 4,000 characters. **This is not a human-readable summary.** Its purpose is to improve BM25 full-text search and semantic vector recall by bridging informal or inconsistent source language to standard AWA/APHIS regulatory terminology.

The retrieval summary is stored in `documents.retrieval_summary` and will be indexed at weight A by the `chunks_fts_trigger` in Phase 3 (higher than raw text at weight B).

Example transformation:
- Raw: `"A responsible adult was not available to accompany APHIS Officials during the inspection process"`
- Summary: `"USDA APHIS inspection access refusal 9 CFR §2.126(b) recordkeeping noncompliance California dealer certificate 93-C-0119 attempted inspection"`

Rules enforced in the prompt:
- Standard regulatory terminology: AWA, 9 CFR Part 2/Part 3, APHIS, Animal Care
- Include species, violation types, CFR section numbers, facility type, certificate/docket numbers
- 150–250 words of keywords and short phrases — not prose
- No legal conclusions, opinions, or case outcomes

---

## Database Writes Summary

| Stage | Table | Column(s) written |
|---|---|---|
| Upload | `documents` | All columns, `status = "pending"` |
| ocr_extract | `documents` | `raw_text`, `status = "processing"` |
| clean | `documents` | `raw_text` (overwrite) |
| classify | `documents` | `doc_type` |
| enrich | `documents` | `retrieval_summary`, `status = "complete"` |
| enrich | `document_metadata` | All metadata columns, `categories` |

---

## Monitoring

Check overall ingest progress:

```bash
docker compose exec api python -c "
import sqlalchemy as sa; from app.config import get_settings
s = get_settings(); e = sa.create_engine(s.sync_database_url)
with e.connect() as c:
    rows = c.execute(sa.text(\"SELECT status, COUNT(*) FROM documents GROUP BY status\")).fetchall()
    [print(r[0], r[1]) for r in rows]
"
```

Watch the worker process tasks in real time:

```bash
docker compose logs -f worker
```

Check for failures:

```bash
docker compose exec api python -c "
import sqlalchemy as sa; from app.config import get_settings
s = get_settings(); e = sa.create_engine(s.sync_database_url)
with e.connect() as c:
    rows = c.execute(sa.text(\"SELECT original_name, error_message FROM documents WHERE status = 'failed'\")).fetchall()
    [print(r) for r in rows]
"
```

---

## Corpus Cost Estimate

Full corpus (~1,562 documents) at gpt-4o-mini pricing:

| Stage | Input tokens | Cost |
|---|---|---|
| classify | ~500 tokens × 1,562 | ~$0.12 |
| metadata_extractor | ~1,000 tokens × 1,562 | ~$0.23 |
| categorizer | ~1,000 tokens × 1,562 | ~$0.23 |
| summarizer | ~1,500 tokens × 1,562 | ~$0.35 |
| **Total** | | **~$1.35** |

---

## What's Next

Phase 3 will chunk each document's `raw_text` into typed segments (`violation`, `finding`, `clause`, `subsection`, `procedure`, `section`) and generate `text-embedding-3-small` embeddings (1536-dim) stored in the `embeddings` table via pgvector. The `chunks_fts_trigger` will auto-populate `fts_vector` for BM25 retrieval.
