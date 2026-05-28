# Phase 4: Hybrid Retrieval Engine

This document covers the search backend built in Phase 4 — the hybrid retrieval system that merges semantic vector search, BM25 full-text search, and metadata pre-filtering into a single ranked result set.

---

## Overview

Phase 4 turns the indexed corpus into a searchable knowledge base. A user query passes through filter + BM25 + vector retrieval, scores are normalized and combined, and the top-K documents are returned with a per-result score breakdown plus LLM-generated match reasoning for the top 5.

```
POST /api/search
  └─→ build SQL filter conditions (doc_type, jurisdiction, categories, …)
  └─→ BM25 search (PostgreSQL tsvector / ts_rank_cd)
  └─→ Vector search (pgvector cosine over text-embedding-3-small embeddings)
  └─→ min-max normalize both score sets to [0, 1]
  └─→ merge: final = 0.6·vector + 0.3·bm25 + 0.1·metadata_boost
  └─→ fetch full document + metadata for top-K
  └─→ annotate top 5 with LLM-generated match reasoning (parallelized)
  └─→ return SearchResponse
```

---

## Pipeline Stages

### 1. Metadata Pre-Filter

`app/retrieval/metadata_filter.py` translates a `SearchRequest` into SQL WHERE conditions over `documents` (alias `d`) joined to `document_metadata` (alias `m`). The conditions are applied identically in both the BM25 and vector queries so the same candidate pool is searched.

Two conditions are always applied:
- `d.status = 'complete'` — never surface in-progress documents
- Parent containers (regulations/policies whose children were split out) are excluded unless `include_parents=true`

### 2. BM25 Search

`app/retrieval/bm25.py` uses PostgreSQL's `websearch_to_tsquery` against the `documents.fts_vector` column. The `fts_vector` is built by a trigger that weights `retrieval_summary` as A and `raw_text` as B, so summary terms dominate the BM25 score. `ts_rank_cd` produces the raw scores; top 100 candidates are returned.

### 3. Vector Search

`app/retrieval/vector.py` embeds the query using `text-embedding-3-small` (the same model used for ingestion), then runs a cosine similarity query against the `embeddings` table using pgvector's `<=>` operator:

```sql
1 - (e.embedding <=> CAST(:query_vector AS vector)) AS score
```

Only document-level embeddings (`chunk_id IS NULL`) are searched. Top 100 candidates are returned.

### 4. Score Merge

`app/retrieval/hybrid.py` independently min-max normalizes the BM25 and vector score dictionaries to [0, 1]:

```
normalized = (score - min) / (max - min)
```

For every document that appeared in either result set:

```
metadata_boost = 1.0 if any metadata filter was applied (and the doc passed), else 0.0
final_score = vector_weight · vector_norm + bm25_weight · bm25_norm + metadata_weight · meta_boost
```

Defaults are **0.6 / 0.3 / 0.1** and are configurable per-request via the `vector_weight`, `bm25_weight`, `metadata_weight` parameters. A document only found by one of the two searches gets 0.0 for the missing component.

### 5. Result Hydration + Reasoning

After the top-K IDs are determined, `hybrid.py` fetches the full document row plus metadata in a single query, then calls `annotate_with_reasoning()` to generate match reasoning for the top 5 results in parallel.

---

## Filter Parameters

All filters are optional. Filters are combined with AND. Multi-value filters (`categories`, `species`) use OR within the field.

| Parameter | Type | Notes |
|---|---|---|
| `query` | string | Required, 1–500 chars |
| `top_k` | int | Default 20, max 100 |
| `doc_type` | enum | `inspection_report` / `regulation` / `policy` / `enforcement_action` |
| `source` | enum | `USDA_APHIS` / `CFR_Title9` / `APHIS_Enforcement` |
| `categories` | array | OR within field (e.g. `["sanitation","housing"]` matches either) |
| `jurisdiction` | string | 2-letter US state code, normalized to uppercase |
| `facility_name` | string | ILIKE partial match |
| `species` | array | OR within field, exact match against `document_metadata.species[]` |
| `inspector_name` | string | ILIKE partial match |
| `reference_number` | string | Exact match (AWA cert or docket number) |
| `date_from` / `date_to` | date | Range over `inspection_date` |
| `include_parents` | bool | Default false — exclude split regulation/policy containers |
| `vector_weight` | float | Default 0.6 |
| `bm25_weight` | float | Default 0.3 |
| `metadata_weight` | float | Default 0.1 |

---

## Response Schema

```json
{
  "query": "veterinary care violations for primates",
  "total_results": 5,
  "results": [
    {
      "id": "uuid",
      "original_name": "...pdf",
      "doc_type": "inspection_report",
      "source": "USDA_APHIS",
      "retrieval_summary": "USDA APHIS conducted a routine inspection of...",
      "parent_document_id": null,
      "metadata": {
        "facility_name": "BTS Research",
        "jurisdiction": "CA",
        "species": ["nonhuman primates"],
        "categories": ["veterinary_care"],
        "inspection_date": "2024-03-28",
        "reference_number": "93-R-0532",
        ...
      },
      "scores": {
        "vector_score": 0.955,
        "bm25_score": 0.203,
        "metadata_boost": 0.0,
        "final_score": 0.634
      },
      "match_reason": "The inspection report identifies veterinary care violations involving nonhuman primates, specifically a failure to euthanize a primate with a breast lump in a timely manner under 9 CFR §2.33(b)(3)..."
    }
  ]
}
```

Every result includes the **score breakdown** — this is non-negotiable per the platform spec, since investigators need to understand why a document ranked where it did.

---

## Match Reasoning

`app/retrieval/reasoning.py` generates a 1–2 sentence explanation of why each top-5 result matches the user's query. It uses `gpt-4o-mini` via the AsyncOpenAI client, parallelized with `asyncio.gather` so all 5 calls happen concurrently.

**Input to the LLM:** the query + the document's retrieval summary + key metadata (facility, species, categories, doc type, jurisdiction). The prompt instructs the model to be specific (cite species, CFR section, violation type) and to omit preamble like "This document matches because…".

**Why top 5 only:** investigators primarily scan the first handful of results; bounding to 5 keeps per-search latency under ~3s and cost negligible (~$0.005 per search).

**Failure handling:** if a reasoning call fails (rate limit, timeout), `match_reason` is left as `null` for that result — the rest of the response is unaffected.

---

## Database Migration

`alembic/versions/f7b8c9d0e1f2_documents_fts_vector.py` added full-text search infrastructure to `documents`:

```sql
ALTER TABLE documents ADD COLUMN fts_vector TSVECTOR;

CREATE FUNCTION documents_fts_update() RETURNS trigger AS $$
BEGIN
  NEW.fts_vector :=
    setweight(to_tsvector('english', coalesce(NEW.retrieval_summary, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(LEFT(NEW.raw_text, 500000), '')), 'B');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_documents_fts_update
  BEFORE INSERT OR UPDATE OF retrieval_summary, raw_text
  ON documents FOR EACH ROW EXECUTE FUNCTION documents_fts_update();

CREATE INDEX idx_documents_fts ON documents USING gin(fts_vector);
```

The trigger fires on insert and on updates to `retrieval_summary` or `raw_text`. `raw_text` is truncated to 500k characters to prevent the tsvector from exceeding PostgreSQL's 1MB column limit on large regulation sections. The migration includes a backfill (`UPDATE documents SET retrieval_summary = retrieval_summary`) to populate `fts_vector` for all 1616 existing documents.

---

## Side Fixes Applied During Phase 4

Three pre-existing Phase 1 bugs surfaced when the search route was first exercised end-to-end:

1. **bcrypt 5.x incompatible with passlib 1.7.4** — pinned `bcrypt==4.2.0` in `requirements.txt`.
2. **`last_login_at` naive vs aware datetime** — `auth.py` now uses `datetime.utcnow()` instead of `datetime.now(timezone.utc)` to match the `TIMESTAMP WITHOUT TIME ZONE` column.
3. **Expired ORM access after commit** — `auth.py` now captures `str(user.id)` and `user.role` into local variables *before* the `UPDATE` + `commit` so subsequent reads don't trigger a session re-fetch in a non-greenlet context.
4. **`pool_pre_ping=True` triggered `MissingGreenlet` errors** under stale connections — `db/session.py` switched to `pool_pre_ping=False, pool_recycle=300`.

---

## Files

| Path | Responsibility |
|---|---|
| `app/schemas/search.py` | SearchRequest, SearchResult, SearchResponse, ScoreBreakdown |
| `app/retrieval/metadata_filter.py` | Build SQL WHERE conditions from filter params |
| `app/retrieval/bm25.py` | tsvector / ts_rank_cd search |
| `app/retrieval/vector.py` | Query embedding + pgvector cosine search |
| `app/retrieval/hybrid.py` | Normalize, merge, rank, hydrate, annotate |
| `app/retrieval/reasoning.py` | Async LLM-generated match reasoning for top 5 |
| `app/api/routes/search.py` | `POST /api/search` authenticated FastAPI endpoint |

---

## How to Test

Three layers:

1. **Inline Python** — call `hybrid_search()` directly with an `AsyncSessionLocal()` session. Bypasses auth.
2. **HTTP API** — login at `POST /api/auth/login` to get a JWT, then `POST /api/search` with the token in the `Authorization: Bearer …` header.
3. **Swagger UI** — open http://localhost:8000/docs, click Authorize, paste the JWT, exercise `/api/search` interactively.

A test user is seeded in dev: `test@example.com` / `test1234`.

---

## Cost & Latency

| Component | Latency | Cost |
|---|---|---|
| BM25 + filter SQL | ~50–150ms | $0 |
| Query embed (text-embedding-3-small) | ~200–400ms | ~$0.00001 |
| Vector cosine search | ~100–300ms | $0 |
| Top-K hydration query | ~30–80ms | $0 |
| Reasoning (5 parallel gpt-4o-mini calls) | ~1.5–2.5s | ~$0.005 |
| **Total per search** | **~2–4s** | **~$0.005** |

Reasoning dominates latency; the underlying retrieval is fast enough to be effectively free.
