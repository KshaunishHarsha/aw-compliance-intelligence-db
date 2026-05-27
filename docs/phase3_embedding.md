# Phase 3: Document Embedding

This document covers the semantic embedding layer built in Phase 3 of the Animal Welfare Compliance Intelligence Platform — how documents are converted into vector representations for semantic search.

---

## Overview

Phase 3 adds a `task_embed` Celery task that runs after `task_enrich` for every document. It builds a text representation of the document from its retrieval summary and structured metadata, calls `text-embedding-3-small` via OpenRouter, and stores the resulting 1536-dimensional vector in the `embeddings` table (backed by pgvector).

```
... → task_enrich [metadata, categories, retrieval summary]
           └─→ task_embed [vector stored in embeddings]
                           [status: complete]
```

---

## Design Decision: Document-Level Embedding

Phase 3 embeds at the **document level** — one vector per document — rather than sub-chunking documents into smaller pieces first.

This is appropriate for this corpus because:

- **Inspection reports** are already atomic units: one facility visit, one set of findings. A single document is the natural retrieval unit.
- **Regulations and policies** are split into sections by the Phase 2 section splitter (Subpart-level for CFR, chapter-level for the Inspection Guide). Each child document is already a naturally scoped chunk.
- **Enforcement actions** are similarly self-contained per respondent and docket.

Sub-chunking at the violation-block or clause level is reserved for a future pass if semantic recall quality turns out to require it.

---

## Embedding Input Construction

The text sent to the embedding model is not raw document text. It is a structured concatenation built by `build_embedding_input()` in `app/ingestion/embedder.py`:

```
{retrieval_summary} {facility_name} {jurisdiction} {species joined} {categories joined} {doc_type}
```

**Example (inspection report):**
```
A routine USDA APHIS inspection of Absorption Systems Inc. (cert. 93-R-0444, CA) on
August 16, 2017, raised concerns regarding the qualifications of a Study Director
performing surgical procedures on sheep, citing issues under 9 CFR §2.31(d)(1)(viii).
The inspection revealed that the Study Director lacked documented primary surgical
experience, and a sheep died during an acute surgical procedure. Additionally, the
facility failed to maintain an anesthetic record for a cat used in a previous protocol,
violating recordkeeping requirements under §2.35(f).
Absorption Systems Inc. CA sheep cats veterinary_care recordkeeping inspection_report
```

The retrieval summary carries most of the semantic signal. The appended metadata fields (facility name, jurisdiction, species, categories) reinforce structured concepts that the summary may express in prose — ensuring that a query for "CA facilities with veterinary care violations involving sheep" matches both the narrative and the structured facts.

Input is capped at 8000 characters (well within the 8191-token limit of `text-embedding-3-small`).

---

## Model

| Setting | Value |
|---|---|
| Model | `text-embedding-3-small` |
| Dimensions | 1536 |
| Provider | OpenRouter (`https://openrouter.ai/api/v1/embeddings`) |
| Config key | `embedding_model` in `Settings` |

The model is configurable via `EMBEDDING_MODEL` environment variable. Changing it requires re-embedding all documents.

---

## Storage

One row per document in the `embeddings` table:

```sql
id UUID PK
chunk_id UUID NULL    -- NULL for document-level embeddings (no sub-chunks)
document_id UUID      -- FK to documents(id) CASCADE
embedding vector(1536)
model TEXT            -- 'text-embedding-3-small'
created_at TIMESTAMPTZ
```

The `chunk_id` column is nullable (migration `e6a7b8c9d0e1`). For document-level embeddings it is always `NULL`. If sub-chunking is added in a future phase, chunk-level embeddings will populate this field.

The IVFFlat index on `embedding` uses cosine distance:

```sql
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

`task_embed` upserts: if an embedding already exists for the document (identified by `document_id` where `chunk_id IS NULL`), it updates the vector. This makes re-embedding safe to re-run.

---

## Pipeline Task

**File:** `app/tasks/ingestion.py` — `task_embed`

```
max_retries: 3
default_retry_delay: 30s
```

The task:
1. Loads the document and its `document_metadata` row.
2. Calls `build_embedding_input()` to construct the embedding text.
3. Skips (logs a warning) if the input is empty — e.g. a document with no retrieval summary yet.
4. Calls `embed()` which hits the OpenRouter embeddings endpoint.
5. Upserts the result into `embeddings`.

Failures are logged with `document_id` context and retried up to 3 times (30s delay). They do not change `documents.status` — the document remains `complete` since the core ingestion (enrich) already succeeded.

---

## Bulk Re-Embedding

To re-embed all complete documents (e.g. after changing the embedding model or input construction):

```bash
docker compose exec api python -c "
from app.tasks.ingestion import task_embed
from sqlalchemy import create_engine, text
from app.config import get_settings
settings = get_settings()
engine = create_engine(settings.sync_database_url)
with engine.connect() as c:
    rows = c.execute(text(\"SELECT id FROM documents WHERE status='complete'\")).fetchall()
    for row in rows:
        task_embed.apply_async(args=[str(row[0])])
    print(f'Queued {len(rows)} embed tasks')
"
```

---

## Schema Migration

Migration `e6a7b8c9d0e1_embeddings_chunk_id_nullable` makes `embeddings.chunk_id` nullable:

```python
def upgrade() -> None:
    op.alter_column("embeddings", "chunk_id", nullable=True)
```

Applied as part of Phase 3 setup: `docker compose exec api alembic upgrade head`

---

## Cost

`text-embedding-3-small` costs approximately $0.02 per million tokens. With an average embedding input of ~200 tokens per document and ~1500 documents in the corpus:

```
1500 docs × 200 tokens = 300,000 tokens ≈ $0.006 total
```

Negligible. Re-embedding the full corpus on model change costs under $0.01.
