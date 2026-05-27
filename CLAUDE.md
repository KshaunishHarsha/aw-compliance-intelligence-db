# Animal Welfare Compliance Intelligence Platform — Claude Context

## What This Is

An open-source AI-powered compliance intelligence platform for animal advocacy organizations, investigators, legal researchers, and NGOs working in animal welfare enforcement.

This is **investigative research software**, not a chatbot. Users search, investigate, and run grounded chat against a shared public corpus of USDA/APHIS documents. The platform surfaces evidence; human experts make decisions.

### Corpus (admin-ingested only, no user uploads in V1)
- USDA APHIS inspection reports
- Animal Welfare Act (AWA) regulations (9 CFR Title 9, Chapter I, Subchapter A)
- APHIS enforcement actions and consent decisions
- APHIS program data and annual summaries
- USDA Animal Welfare Inspection Guide

### Primary Users
Animal advocacy NGOs, investigators, compliance analysts, policy researchers, legal teams.

---

## Tech Stack — Do Not Suggest Alternatives

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), Tailwind CSS, react-pdf, TypeScript |
| Backend | FastAPI (Python 3.11+), Pydantic v2 |
| Async | Redis (broker) + Celery (workers) |
| Database | PostgreSQL 15+ with pgvector extension |
| FTS | PostgreSQL tsvector/tsquery (BM25-style) |
| File Storage | Supabase Storage, single bucket: `documents`, signed URLs (1-hour) |
| AI/LLM | OpenAI: `text-embedding-3-small` (1536-dim), `gpt-4o-mini` (metadata/categorization/summaries), `gpt-4o` (grounded chat) |
| PDF extraction | PyMuPDF + Tesseract (OCR for scanned PDFs) |
| Hosting | Railway (API + workers), Supabase (Postgres + Storage) |
| Dev | Docker Compose (Postgres, pgvector, Redis, API, worker) |

---

## Auth Model

Two roles only — no org structure, no multi-tenancy, no per-user data isolation.

| Role | Permissions |
|---|---|
| `superadmin` | Ingest documents, manage users, trigger re-ingestion |
| `user` | Search, view documents, grounded chat |

- JWT tokens, 24-hour expiry, refresh token rotation
- Tokens invalidated on logout via Redis blocklist

---

## Database Schema — Do Not Restructure Without Asking

### `users`
```sql
id UUID PK, email TEXT UNIQUE, hashed_password TEXT, full_name TEXT,
role TEXT DEFAULT 'user' -- 'superadmin' | 'user'
is_active BOOLEAN, last_login_at TIMESTAMPTZ, created_at, updated_at
```

### `documents`
```sql
id UUID PK, filename TEXT, original_name TEXT, file_path TEXT (Supabase path),
file_size BIGINT, mime_type TEXT,
status TEXT -- pending | processing | complete | failed
error_message TEXT, doc_type TEXT, source TEXT, raw_text TEXT,
retrieval_summary TEXT, ingested_by UUID -> users(id), created_at, updated_at
```
Doc types: `inspection_report`, `regulation`, `policy`, `enforcement_action`
Sources: `USDA_APHIS`, `CFR_Title9`, `APHIS_Enforcement`

> **Note:** The Phase 1 model uses `uploaded_by` instead of `ingested_by`. The pre-Phase-2 migration must rename this column to match the authoritative schema.

### `document_metadata`
```sql
id UUID PK, document_id UUID -> documents(id) CASCADE,
issuer TEXT, jurisdiction TEXT, facility_name TEXT,
species TEXT[], inspection_date DATE, inspector_name TEXT,
reference_number TEXT, categories TEXT[], extra JSONB, created_at
```
Valid categories: `overcrowding`, `veterinary_care`, `transport_conditions`, `sanitation`, `water_access`, `euthanasia`, `housing`, `feeding`, `handling`, `recordkeeping`

GIN indexes on `species` and `categories`.

### `chunks`
```sql
id UUID PK, document_id UUID -> documents(id) CASCADE,
chunk_index INTEGER, chunk_type TEXT, page_number INTEGER,
raw_text TEXT, retrieval_summary TEXT, token_count INTEGER,
fts_vector TSVECTOR (managed by trigger, never set by app), created_at
```
Chunk types by doc_type:
- `inspection_report` → `violation` / `finding`
- `regulation` → `clause` / `subsection`
- `policy` → `procedure` / `section`
- `enforcement_action` → `finding` / `section`

Every chunk MUST carry: `document_id`, `chunk_index`, `chunk_type`, `page_number`.

### `embeddings`
```sql
id UUID PK, chunk_id UUID -> chunks(id) CASCADE (nullable — NULL for document-level embeddings),
document_id UUID -> documents(id) CASCADE,
embedding vector(1536), model TEXT DEFAULT 'text-embedding-3-small', created_at
```
IVFFlat index with `lists = 100`, cosine ops.

> **Phase 3 note:** We embed at **document level** (one embedding per document), not chunk level. `chunk_id` is nullable. The embedding input is: `retrieval_summary + facility_name + species + categories` concatenated. The `chunks` table is reserved for a future sub-chunking pass if recall quality requires it.

### FTS Trigger
`fts_vector` is built by a DB trigger. `retrieval_summary` → weight A, `raw_text` → weight B. **Never populate `fts_vector` from application code.**

---

## Retrieval Summary — What It Is

A short (3–5 sentence) **human-readable** prose summary that helps investigators quickly understand a document and decide whether to open it. It names the facility, state, date, primary issue, specific CFR sections, and species involved.

It is also the primary input for semantic embedding — so it must be both readable and keyword-rich in AWA/CFR terminology. It is **not** a keyword dump.

Example: "A routine USDA APHIS inspection of Lucky Rabbits Inc. (cert. 93-B-0242, CA) on July 11, 2016 identified repeat violations under 9 CFR §3.50(a), §3.51(d), and §3.53 related to uncovered light bulbs over enclosures, rusted housing structures, and damaged wire floors that could injure the rabbits. Original correction dates had passed without full resolution."

---

## Hybrid Retrieval Engine (`app/retrieval/hybrid.py`)

```
1. Metadata pre-filter (SQL WHERE on document_metadata)
2. BM25 (tsvector) + vector similarity (pgvector cosine) — run in parallel
3. Normalize both score sets to [0, 1] via min-max
4. final_score = 0.6 * vector_score + 0.3 * bm25_score + 0.1 * metadata_boost
5. Sort descending, return top-K with score breakdown
```

**Score breakdown (vector_score, bm25_score, final_score) must be in every retrieval response.**

Default weights (0.6 / 0.3 / 0.1) must be **configurable, not hardcoded**. Do not change defaults without being asked.

---

## Ingestion Pipeline (Celery chain)

```
upload to Supabase Storage
→ create document row (status: pending)
→ ocr_extract → clean → classify → section_split → enrich → embed
```

- `section_split`: regulation/policy docs are split into child Document rows (one per Part/Subpart/chapter); parent marked complete. Inspection reports and enforcement actions pass straight through to enrich.
- `enrich`: metadata extraction + categorization + retrieval summary (all three LLM calls in one task).
- `embed`: builds embedding input from `retrieval_summary + metadata fields`, calls `text-embedding-3-small`, stores one row in `embeddings` per document.

- Each stage updates `documents.status`; failures write to `documents.error_message` prefixed with stage name (`"ocr_extract: ..."`)
- Each stage receives `document_id` and reads/writes the document record
- Stages are independently retryable
- If PyMuPDF extracts < 100 characters from a PDF → treat as scanned, run Tesseract OCR

---

## Grounded Document Chat — Hard Constraints

Chat is scoped to (a) a single document or (b) a specific result set. No global/unscoped chat.

Every response MUST:
- Cite specific chunk IDs and page numbers for every claim
- Refuse to draw legal conclusions
- Refuse claims not supported by retrieved chunks
- Stay within scope of selected document or result set
- Frame findings as potential observations, not confirmed violations

These are enforced via system prompt and are non-negotiable product requirements.

---

## Project Structure

```
/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/routes/
│   │   │   ├── auth.py          -- login, logout, refresh
│   │   │   ├── users.py         -- user management (superadmin only)
│   │   │   ├── documents.py     -- list, view, delete
│   │   │   ├── ingest.py        -- trigger ingestion (superadmin only)
│   │   │   ├── search.py        -- hybrid retrieval
│   │   │   └── chat.py          -- grounded RAG chat
│   │   ├── api/deps.py          -- get_current_user, require_superadmin
│   │   ├── ingestion/           -- ocr, cleaner, classifier, metadata_extractor,
│   │   │                           categorizer, summarizer, chunker, embedder
│   │   ├── retrieval/           -- hybrid.py, bm25.py, vector.py, metadata_filter.py
│   │   ├── chat/rag.py
│   │   ├── models/              -- user.py, document.py (SQLAlchemy)
│   │   ├── schemas/             -- Pydantic v2 schemas
│   │   ├── tasks/ingestion.py   -- Celery tasks
│   │   ├── db/session.py        -- SQLAlchemy engine + session
│   │   └── storage/client.py    -- Supabase Storage client
│   ├── tests/                   -- mirrors app/ structure
│   ├── alembic/                 -- migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/(auth)/login, logout/
│   ├── app/search/
│   ├── app/documents/[id]/
│   ├── components/search/, document/, chat/
│   └── lib/api.ts               -- typed API client
├── docker-compose.yml
└── .env.example
```

---

## Build Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation — scaffold, schema, infra, Docker Compose | ✅ Complete |
| 2 | Ingestion Pipeline — OCR through retrieval summary + bulk ingest | ✅ Complete |
| 3 | Embedding — document-level vectors via text-embedding-3-small, stored in pgvector | ✅ Complete |
| 4 | Hybrid Retrieval Engine — BM25 + vector + metadata merged | Not started |
| 5 | Investigation Interface — search UI, PDF viewer, filters | Not started |
| 6 | Grounded Document Chat — scoped RAG with citations | Not started |
| 7 | Hardening + Deployment — error handling, observability, Railway | Not started |

**Phase 3 notes:**
- Embedding is document-level (one vector per document, `chunk_id = NULL`). The `chunks` table is unused for now.
- Embedding input: `retrieval_summary + facility_name + jurisdiction + species + categories + doc_type` concatenated.
- Migration `e6a7b8c9d0e1` makes `embeddings.chunk_id` nullable to support document-level rows.
- `task_embed` fires from within `task_enrich` after commit. Max 3 retries, does not change `documents.status` on failure.
- To re-embed all docs: queue `task_embed` for every `status='complete'` document (see `docs/phase3_embedding.md`).

**Phase 2 notes:**
- Pre-Phase-2 Alembic migration applied: dropped org tables, renamed `uploaded_by` → `ingested_by`, added `source` column, fixed `inspection_date` type, added all indexes.
- `parent_document_id` migration applied: self-referential FK on `documents`; regulation/policy docs split into child sections, parent marked complete as a provenance container.
- LLM calls use OpenRouter (not direct OpenAI): `base_url="https://openrouter.ai/api/v1"`, models `openai/gpt-4o-mini` (pipeline) and `openai/gpt-4o` (chat). Config via `openrouter_api_key`, `llm_mini_model`, `llm_chat_model` in Settings.
- `scripts/bulk_ingest.py` ingests the local `corpus/` directory (mounted at `/app/corpus` in containers). Run inside the api container: `docker compose exec api python scripts/bulk_ingest.py [--limit N] [--dry-run]`.
- API `GET /documents` defaults to leaf documents only (`include_parents=false`). Pass `parent_id=<uuid>` to list children of a split document.

---

## Code Conventions

- Python: type hints everywhere, no bare `except`, Pydantic models for all I/O
- All DB queries through SQLAlchemy ORM — no raw SQL strings in route handlers
- Raw SQL acceptable inside `retrieval/` where intentional query construction is needed
- Environment variables via `pydantic-settings` BaseSettings — never `os.environ.get()`
- Every Celery task logs entry, exit, and exceptions with `document_id` as context
- No `print()` — use Python `logging` with structured fields
- Frontend: TypeScript strict mode, no `any`, all API calls through typed client in `lib/api.ts`
- Tests in `backend/tests/`, mirroring `app/` structure

---

## When to Ask Before Acting

1. **Schema changes** — always ask first; downstream consequences across ingestion, retrieval, API
2. **New dependencies** — ask and justify
3. **Chunking logic** — ask if a doc structure doesn't fit defined chunk types; do not invent new chunk types
4. **OpenAI prompts** — show the prompt before wiring into a pipeline stage
5. **Retrieval weights** — do not change defaults (0.6/0.3/0.1) without being asked

---

## What This System Does NOT Do

- Accept document uploads from end users (V2)
- Provide legal advice or automated legal conclusions
- Make compliance determinations or risk scores
- Agentic AI workflows
- Global/unscoped chat
- Black-box decision making
