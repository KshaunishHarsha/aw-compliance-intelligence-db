# Animal Welfare Compliance Intelligence Platform

Investigative research software for animal advocacy organizations, compliance analysts, legal teams, and policy researchers working against the USDA APHIS corpus of inspection reports, regulations, policy guidance, and enforcement actions.

> The platform surfaces evidence; human experts make decisions.

---

## What it does

Search **1,617 USDA APHIS documents** — inspection reports, 9 CFR Title 9 regulations, the APHIS Animal Welfare Inspection Guide, and enforcement actions — to find the cases, citations, and patterns relevant to your investigation. Then ask grounded questions about any document and get answers that cite back to the source.

| Capability | Where |
|---|---|
| **Hybrid search** — vector + BM25 + metadata | `/search` |
| **Document detail** with metadata panel + PDF viewer | `/documents/[id]` |
| **Page-jumping** for regulation subparts | Auto on split-section documents |
| **Grounded chat** with citations | "Ask about this document" on detail pages, or `/chat` |
| **Browse** the corpus | `/documents` |
| **Living design system** | `/design` |

---

## The retrieval engine (the moat)

Every query runs through three signals **in parallel**:

1. **Vector embeddings** (`text-embedding-3-small`, document-level, stored in pgvector) — catches semantic intent. A query like *"animals denied water"* finds passages that actually say *"inadequate potable water access under 9 CFR §3.9."*
2. **BM25 full-text search** (PostgreSQL `tsvector` with weighted retrieval summary + raw text) — catches exact regulatory citations and proper nouns.
3. **Structured metadata filter** (jurisdiction, species, categories, date range, facility name) — narrows the candidate pool to what matters.

Scores are min-max normalized and merged:

```
final = 0.6 · vector + 0.3 · bm25 + 0.1 · metadata_boost
```

The top 5 results carry an LLM-generated explanation of *why* they matched, so investigators don't have to guess at relevance.

---

## Grounded chat — three non-negotiable constraints

1. **No legal conclusions.** Never declares a violation, never labels as compliant, never renders a verdict.
2. **No unsupported claims.** If the retrieved passages don't answer the question, the model says so.
3. **Observational framing only.** *"The report notes…"*, *"the inspector documented…"* — never as established fact.

Enforced in three layers: a strong system prompt, retrieval bounded to the scoped document's text, and post-hoc citation validation in the route handler.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router, Turbopack), Tailwind v4, React 19, TypeScript |
| Display fonts | Fraunces (editorial), IBM Plex Sans (UI), IBM Plex Mono (citations) |
| PDF viewer | `react-pdf` v10 (worker pinned, `next/dynamic` `ssr:false`) |
| Backend | FastAPI (Python 3.11), Pydantic v2 |
| Async | Redis + Celery (workers handle ingestion, not chat) |
| Database | PostgreSQL 17 with `pgvector` |
| FTS | PostgreSQL `tsvector` + GIN index, trigger-managed |
| Storage | Supabase Storage (signed URLs, 1-hour TTL) |
| LLM | OpenAI via OpenRouter — `text-embedding-3-small` for vectors, `gpt-4o-mini` for metadata/summaries/match-reasoning, `gpt-4o` for chat |
| OCR | PyMuPDF + Tesseract fallback |
| Dev | Docker Compose (Postgres, pgvector, Redis, API, worker) |
| Hosting | **Railway** (API + Redis) + **Supabase** (Postgres + Storage) + **Vercel** (Next.js) |

---

## Architecture

```
        ┌──────────────────┐
        │  Vercel (CDN)    │   Next.js 16 — static + RSC
        │  *.vercel.app    │   NEXT_PUBLIC_API_URL → Railway
        └────────┬─────────┘
                 │ HTTPS
                 ▼
        ┌──────────────────┐
        │  Railway         │   FastAPI (uvicorn) + Celery worker + Redis
        │  *.railway.app   │   All env vars live here
        └────────┬─────────┘
                 │ Session pooler (Supavisor :5432)
                 ▼
        ┌──────────────────┐
        │  Supabase        │   Postgres 17 + pgvector + Storage bucket
        │  ap-southeast-1  │   FK/trigger/index schema in alembic/
        └──────────────────┘
```

---

## Local Development

```bash
# 1. Backend services (Postgres, Redis, API, Celery worker)
docker compose up -d

# 2. Apply migrations (only needed once)
docker compose exec api alembic upgrade head

# 3. Frontend dev server
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 → redirects to `/login`.

**Seeded dev credentials:** `test@example.com` / `test1234`

---

## Environment Variables

### Backend (`backend/.env`)

```env
# Database (local Docker postgres or Supabase)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/compliance_db
SYNC_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/compliance_db

# Redis (Celery broker + rate limit store)
REDIS_URL=redis://redis:6379/0

# LLM (via OpenRouter)
OPENROUTER_API_KEY=<your key>

# Storage
STORAGE_PROVIDER=supabase
SUPABASE_URL=<your supabase project URL>
SUPABASE_KEY=<your service-role key>
SUPABASE_BUCKET=documents

# App
ENVIRONMENT=development
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(48))">
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Adding Users

There's no UI for user management yet — V1 deferred that. Add users via SQL on Supabase or via a one-off Python script:

### SQL (Supabase SQL Editor)

```sql
INSERT INTO users (email, hashed_password, full_name, role, is_active)
VALUES (
  'name@example.com',
  crypt('StrongPasswordHere', gen_salt('bf', 12)),
  'Full Name',
  'user',          -- or 'superadmin'
  true
);
```

Requires the `pgcrypto` extension (already enabled). The bcrypt hash is compatible with `passlib + bcrypt==4.2.0`.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/routes/          # auth, users, documents, ingest, search, chat
│   │   ├── api/deps.py          # auth dependencies
│   │   ├── chat/rag.py          # grounded chat RAG pipeline
│   │   ├── ingestion/           # OCR, cleaner, classifier, splitter, embedder
│   │   ├── retrieval/           # hybrid.py, bm25.py, vector.py, metadata_filter.py
│   │   ├── observability/       # request ID, JSON logging, rate limiter
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic v2 schemas
│   │   └── tasks/ingestion.py   # Celery tasks
│   ├── alembic/                 # 8 migrations
│   ├── scripts/                 # bulk_ingest, backfill helpers
│   └── Dockerfile               # production-ready (used by Railway)
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (app)/           # AuthGuard-wrapped routes
│   │   │   │   ├── search/
│   │   │   │   ├── documents/
│   │   │   │   └── chat/
│   │   │   ├── login/
│   │   │   └── design/          # living style guide
│   │   ├── components/          # app-shell, search, document, chat
│   │   └── lib/api.ts           # typed API client
│   └── next.config.ts
├── docs/                        # phase1 … phase7 design + architecture docs
├── corpus/                      # local PDFs (1,617 files) — admin-only
├── docker-compose.yml
└── CLAUDE.md                    # project context for AI coding tools
```

---

## Build Phases (project status)

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation — scaffold, schema, Docker Compose | ✅ |
| 2 | Ingestion Pipeline — OCR → clean → classify → section split → enrich | ✅ |
| 3 | Embedding — document-level vectors via `text-embedding-3-small` | ✅ |
| 4 | Hybrid Retrieval — BM25 + vector + metadata + LLM match reasoning | ✅ |
| 5 | Investigation Interface — design system, app shell, search, document detail with PDF viewer, browse | ✅ |
| 6 | Grounded Chat — document-scoped RAG with SSE streaming + citation pills + conversation history | ✅ (V1.0) |
| 7 | Hardening + Deployment — observability, rate limit, error JSON, production guard + Railway + Vercel + Supabase Postgres | ✅ |

Full design and decisions per phase live in [`docs/`](./docs).

---

## Documentation

- [`docs/phase1_foundation.md`](./docs/phase1_foundation.md)
- [`docs/phase2_ingestion_pipeline.md`](./docs/phase2_ingestion_pipeline.md)
- [`docs/phase3_embedding.md`](./docs/phase3_embedding.md)
- [`docs/phase4_hybrid_retrieval.md`](./docs/phase4_hybrid_retrieval.md)
- [`docs/phase5_investigation_interface.md`](./docs/phase5_investigation_interface.md)
- [`docs/phase6_grounded_chat.md`](./docs/phase6_grounded_chat.md)
- [`docs/phase7_deployment.md`](./docs/phase7_deployment.md)
- [`CLAUDE.md`](./CLAUDE.md) — project context for AI coding tools

---

## What this system does NOT do

- Accept document uploads from end users (admin-ingested only in V1)
- Provide legal advice or automated legal conclusions
- Make compliance determinations or risk scores
- Agentic AI workflows
- Global / unscoped chat (chat is always scoped to a specific document)
- Black-box decision making — every result carries a score breakdown, every chat answer carries citations

---

## License

To be determined. Treat as proprietary until specified.
