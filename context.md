# Project Context: Animal Welfare Compliance Intelligence Platform

You are helping me build an open-source AI-powered compliance intelligence platform for animal advocacy organizations, investigators, legal researchers, and NGOs working in animal welfare enforcement.

Read this entire document before writing any code or making any architectural suggestions. Every decision recorded here was made deliberately. Do not suggest alternatives to settled decisions unless I ask.

---

## What This Is

An investigative intelligence and retrieval platform for animal welfare compliance documents. Users search, analyze, and investigate large collections of:

- USDA inspection reports
- Animal Welfare Act (AWA) regulations
- Enforcement actions
- Internal policies
- Compliance reports
- NGO investigations

This is NOT a chatbot. It is NOT "ChatGPT over PDFs." It is closer to investigative research software — a searchable compliance intelligence system with grounded AI assistance.

### What the system does NOT do
- Provide legal advice or automated legal conclusions
- Autonomous compliance decisions or risk scoring
- Agentic AI workflows
- Black-box decision making
- Open-ended hallucination-prone AI behavior

### What the system prioritizes
- Retrieval quality over AI sophistication
- Citations and evidence traceability over fluent-sounding responses
- Explainability at every layer
- Hybrid search quality (semantic + keyword + metadata together)
- Investigation workflows over conversational UX

---

## Primary Users

- Animal advocacy NGOs
- Investigators and compliance analysts
- Policy researchers
- Legal teams

These users work with limited staffing, fragmented datasets, thousands of pages of inspection reports, inconsistent regulatory standards, and difficult manual review workflows.

---

## Tech Stack — Settled, Do Not Suggest Alternatives

**Frontend**
- Next.js (App Router)
- Tailwind CSS
- react-pdf (PDF rendering)
- TypeScript

**Backend**
- FastAPI (Python)
- Pydantic v2 for schemas
- Python 3.11+

**Async Processing**
- Redis (queue broker)
- Celery (workers)

**Database**
- PostgreSQL 15+
- pgvector extension (vector similarity search)
- Full-text search via PostgreSQL tsvector/tsquery (BM25-style)

**File Storage**
- AWS S3 or Supabase Storage (abstracted behind a storage interface so the provider is swappable)

**AI / LLM**
- OpenAI API
  - `text-embedding-3-small` for embeddings (1536 dimensions)
  - `gpt-4o-mini` for metadata extraction, categorization, retrieval summary generation
  - `gpt-4o` for grounded document chat
- PyMuPDF (native PDF text extraction)
- Tesseract (OCR for scanned PDFs)
- python-docx (DOCX extraction)

**Hosting**
- Railway (API + Celery workers)
- Supabase or Neon (managed Postgres)

**Dev Environment**
- Docker Compose for local development (Postgres, pgvector, Redis, API, worker all in one command)

---

## System Architecture — High-Level Flow

```
Documents Uploaded / Ingested
↓
OCR + Text Extraction (PyMuPDF + Tesseract)
↓
Text Cleaning + Normalization
↓
Document Type Classification (inspection / regulation / policy / enforcement)
↓
Metadata Extraction         Multi-label Categorization     Retrieval Summary Generation
↓                           ↓                              ↓
                    (all feed into PostgreSQL)
↓
Chunking Engine (document-type-aware)
↓
Embedding Generation (OpenAI text-embedding-3-small)
↓
Stored in PostgreSQL + pgvector
↓
Hybrid Retrieval Engine (metadata filter + BM25 + vector similarity → reranker)
↓
Investigation Interface (search → results → document view)
↓
Grounded Document Chat (scoped RAG, citations required)
```

---

## Database Schema — Authoritative

These are the core tables. Do not restructure them without being asked.

### `documents`
```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        TEXT NOT NULL,
    original_name   TEXT NOT NULL,
    file_path       TEXT NOT NULL,           -- S3/Supabase storage path
    file_size       BIGINT,
    mime_type       TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending | processing | complete | failed
    error_message   TEXT,
    doc_type        TEXT,
                    -- inspection_report | regulation | policy | enforcement_action
    raw_text        TEXT,                    -- full extracted text post-OCR
    retrieval_summary TEXT,                  -- keyword-heavy normalized summary
    uploaded_by     UUID,                    -- FK to users table (future)
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### `document_metadata`
```sql
CREATE TABLE document_metadata (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    issuer          TEXT,
    jurisdiction    TEXT,
    facility_name   TEXT,
    species         TEXT[],                  -- array: ['Chicken', 'Cattle']
    inspection_date DATE,
    inspector_name  TEXT,
    reference_number TEXT,
    categories      TEXT[],
                    -- ['overcrowding', 'water_access', 'transport_conditions', ...]
    extra            JSONB,                  -- overflow for future metadata fields
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

Valid category values: `overcrowding`, `veterinary_care`, `transport_conditions`,
`sanitation`, `water_access`, `euthanasia`, `housing`, `feeding`, `handling`, `recordkeeping`

### `chunks`
```sql
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,        -- ordering within document
    chunk_type      TEXT NOT NULL,
                    -- violation | finding | clause | subsection | procedure | section
    page_number     INTEGER,                 -- source page in original PDF
    raw_text        TEXT NOT NULL,
    retrieval_summary TEXT,                  -- per-chunk normalized text (optional)
    token_count     INTEGER,
    fts_vector      TSVECTOR,               -- populated by trigger or on insert
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_fts ON chunks USING GIN(fts_vector);
```

### `embeddings`
```sql
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id        UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    embedding       vector(1536) NOT NULL,
    model           TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_embeddings_chunk_id ON embeddings(chunk_id);
CREATE INDEX idx_embeddings_vector ON embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### FTS trigger (populate fts_vector automatically)
```sql
CREATE OR REPLACE FUNCTION chunks_fts_update() RETURNS trigger AS $$
BEGIN
    NEW.fts_vector :=
        setweight(to_tsvector('english', coalesce(NEW.retrieval_summary, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.raw_text, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chunks_fts_trigger
    BEFORE INSERT OR UPDATE ON chunks
    FOR EACH ROW EXECUTE FUNCTION chunks_fts_update();
```

---

## Chunking Strategy — Document-Type-Aware

Chunking is NOT arbitrary token splitting. The strategy depends on doc_type.

| doc_type | chunk_type | Unit of meaning |
|---|---|---|
| `inspection_report` | `violation` / `finding` | Each numbered finding or cited violation |
| `regulation` | `clause` / `subsection` | Each numbered regulatory provision |
| `policy` | `procedure` / `section` | Each operational procedure or section heading |
| `enforcement_action` | `finding` / `section` | Each cited finding or order section |

Every chunk MUST carry: `document_id`, `chunk_index`, `chunk_type`, `page_number`.

---

## Hybrid Retrieval Engine

The retrieval system combines three signals. This logic lives in `app/retrieval/hybrid.py`.

```
User Query
↓
1. Metadata pre-filter (SQL WHERE on document_metadata)
↓
2. BM25 / Full-text search (PostgreSQL tsvector, returns scores)
   +
   Vector similarity search (pgvector cosine, returns scores)
↓
3. Normalize both score sets independently to [0, 1] via min-max
↓
4. Hybrid score merge:
   final_score = 0.6 * vector_score + 0.3 * bm25_score + 0.1 * metadata_boost
↓
5. Sort descending, return top-K chunks with score breakdown
```

The score breakdown (vector_score, bm25_score, final_score) must be returned in every
retrieval response — it is used for explainability in the UI.

Weights (0.6 / 0.3 / 0.1) are defaults. They should be configurable, not hardcoded.

---

## Retrieval Summary — What It Is and Why

Each document (and optionally each chunk) has a `retrieval_summary`. This is NOT a
human-readable summary. It is a keyword-heavy, normalized-terminology artifact that
improves BM25 and semantic recall by bridging inconsistent source language.

Example:
- Raw text: "hens unable to access hydration infrastructure"
- Retrieval summary: "poultry water access violations during transport"

The FTS trigger weights retrieval_summary as 'A' (higher) and raw_text as 'B' (lower)
precisely because retrieval summaries contain normalized regulatory terminology.

---

## Grounded Document Chat — Constraints

The chat system is scoped to either (a) a single document or (b) a specific result set.
Global/unscoped chat does not exist in this system.

Every chat response MUST:
- Cite specific chunk IDs and page numbers for every claim
- Refuse to draw legal conclusions
- Refuse to make claims not supported by the retrieved chunks
- Stay within the scope of the selected document or result set

The system prompt enforces these constraints. They are non-negotiable product requirements,
not suggestions.

---

## Ingestion Pipeline — Stage Sequence

```
upload → ocr_extract → clean → classify → [metadata, categorize, summarize] → chunk → embed
```

Each stage updates `documents.status`. Failures are logged to `documents.error_message`
with the stage name prefix (e.g. `"ocr_extract: PyMuPDF failed with..."`).

Pipeline stages run as Celery tasks chained together. Each stage receives a `document_id`
and reads/writes the document record. Stages are independently retryable.

Scanned PDF detection: if PyMuPDF extracts fewer than 100 characters from a PDF, treat
it as scanned and run Tesseract OCR.

---

## Project Structure (Expected)

```
/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── documents.py
│   │   │   │   ├── search.py
│   │   │   │   └── chat.py
│   │   ├── ingestion/
│   │   │   ├── ocr.py
│   │   │   ├── cleaner.py
│   │   │   ├── classifier.py
│   │   │   ├── metadata_extractor.py
│   │   │   ├── categorizer.py
│   │   │   ├── summarizer.py
│   │   │   ├── chunker.py
│   │   │   └── embedder.py
│   │   ├── retrieval/
│   │   │   ├── hybrid.py
│   │   │   ├── bm25.py
│   │   │   ├── vector.py
│   │   │   └── metadata_filter.py
│   │   ├── chat/
│   │   │   └── rag.py
│   │   ├── models/          -- SQLAlchemy ORM models
│   │   ├── schemas/         -- Pydantic request/response schemas
│   │   ├── tasks/           -- Celery task definitions
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── migrations/  -- Alembic
│   │   └── storage/
│   │       └── client.py    -- S3/Supabase abstraction
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   ├── search/
│   │   ├── documents/
│   │   │   └── [id]/
│   │   └── upload/
│   ├── components/
│   │   ├── search/
│   │   ├── document/
│   │   └── chat/
│   └── lib/
│
├── docker-compose.yml
└── .env.example
```

---

## Build Phases — Current Status

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation — scaffold, schema, infra, Docker Compose | Not started |
| 2 | Ingestion Pipeline — upload through retrieval summary | Not started |
| 3 | Chunking + Embedding — chunks stored in pgvector | Not started |
| 4 | Hybrid Retrieval Engine — BM25 + vector + metadata merged | Not started |
| 5 | Investigation Interface — search UI, PDF viewer, filters | Not started |
| 6 | Grounded Document Chat — scoped RAG with citations | Not started |
| 7 | Hardening + Deployment — error handling, observability, Railway | Not started |

When I tell you which phase we are working on, focus exclusively on that phase.
Do not build ahead into future phases unless I ask. Do not refactor completed phases
unless a current phase requirement makes it unavoidable.

---

## Code Conventions

- Python: type hints everywhere, no bare `except`, Pydantic models for all I/O
- All database queries go through SQLAlchemy — no raw SQL strings in route handlers
- Raw SQL is acceptable inside `retrieval/` files where query construction is intentional
- Environment variables via `pydantic-settings` BaseSettings — no `os.environ.get()` scattered around
- Every Celery task logs entry, exit, and any exception with the `document_id` as context
- No print statements — use Python `logging` with structured fields
- Frontend: TypeScript strict mode, no `any`, API calls through a typed client in `lib/api.ts`
- Tests live in `backend/tests/`, mirroring the `app/` structure

---

## What To Do When You Are Unsure

1. **Schema changes** — ask before making them. Schema changes have downstream consequences across ingestion, retrieval, and the API.
2. **New dependencies** — ask before adding them. Justify the addition.
3. **Chunking logic** — ask if a document structure doesn't fit the defined chunk types. Do not invent new chunk types silently.
4. **OpenAI prompts** — show me the prompt before wiring it into a pipeline stage. Prompt quality determines data quality for every downstream feature.
5. **Retrieval weights** — do not change the default hybrid weights (0.6/0.3/0.1) without being asked.

When in doubt, write the code so the decision is visible and easy to change, then flag it.