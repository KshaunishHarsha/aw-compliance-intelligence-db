import logging
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.bm25 import bm25_search
from app.retrieval.metadata_filter import build_filter_conditions, where_clause
from app.retrieval.reasoning import annotate_with_reasoning
from app.retrieval.vector import vector_search
from app.schemas.search import ScoreBreakdown, SearchResult, SearchResponse, SearchResultMetadata

logger = logging.getLogger(__name__)

_CANDIDATE_LIMIT = 100  # candidates fetched from each search before merging


def _has_active_filters(params: Any) -> bool:
    return bool(
        params.jurisdiction or params.facility_name or params.species or
        params.categories or params.date_from or params.date_to or
        params.inspector_name or params.reference_number or
        params.doc_type or params.source
    )


def _has_query(params: Any) -> bool:
    return bool(params.query and params.query.strip())


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a score dict to [0, 1]."""
    if not scores:
        return {}
    min_s = min(scores.values())
    max_s = max(scores.values())
    span = max_s - min_s
    if span == 0:
        return {k: 1.0 for k in scores}
    return {k: (v - min_s) / span for k, v in scores.items()}


def _build_result(row: Any, scores: ScoreBreakdown) -> SearchResult:
    return SearchResult(
        id=row[0],
        original_name=row[1],
        doc_type=row[2],
        source=row[3],
        retrieval_summary=row[4],
        parent_document_id=row[5],
        metadata=SearchResultMetadata(
            issuer=row[6],
            jurisdiction=row[7],
            facility_name=row[8],
            species=row[9],
            inspection_date=row[10],
            inspector_name=row[11],
            reference_number=row[12],
            categories=row[13],
            extra=row[14],
        ),
        scores=scores,
    )


async def hybrid_search(db: AsyncSession, params: Any) -> SearchResponse:
    has_query = _has_query(params)
    has_filters = _has_active_filters(params)

    if not has_query and not has_filters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a search query or at least one filter.",
        )

    if not has_query:
        return await _filter_only_search(db, params)

    return await _query_search(db, params, has_filters)


# ── Filter-only mode ──────────────────────────────────────────────────────────

async def _filter_only_search(db: AsyncSession, params: Any) -> SearchResponse:
    """
    No query — return documents matching filters, ordered by inspection_date desc.
    Skips BM25, vector search, and LLM reasoning. Scores reflect: metadata-only
    match, so vector/bm25 = 0, metadata_boost = 1.0, final_score = metadata_weight.
    """
    filter_conditions, filter_params = build_filter_conditions(params)
    w_clause = where_clause(filter_conditions)

    sql = text(f"""
        SELECT
            d.id, d.original_name, d.doc_type, d.source,
            d.retrieval_summary, d.parent_document_id,
            m.issuer, m.jurisdiction, m.facility_name,
            m.species, m.inspection_date, m.inspector_name,
            m.reference_number, m.categories, m.extra
        FROM documents d
        LEFT JOIN document_metadata m ON m.document_id = d.id
        {w_clause}
        ORDER BY m.inspection_date DESC NULLS LAST, d.created_at DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {**filter_params, "limit": params.top_k})
    rows = result.fetchall()

    final = round(params.metadata_weight, 4)
    scores = ScoreBreakdown(
        vector_score=0.0,
        bm25_score=0.0,
        metadata_boost=1.0,
        final_score=final,
    )
    results = [_build_result(r, scores) for r in rows]

    logger.info(
        "hybrid_search (filter-only) complete",
        extra={"returned": len(results), "top_k": params.top_k},
    )

    return SearchResponse(
        query=params.query or "",
        total_results=len(results),
        results=results,
    )


# ── Query mode (with optional filters) ────────────────────────────────────────

async def _query_search(db: AsyncSession, params: Any, has_filters: bool) -> SearchResponse:
    filter_conditions, filter_params = build_filter_conditions(params)

    bm25_raw = await bm25_search(db, params.query, filter_conditions, filter_params, _CANDIDATE_LIMIT)
    vector_raw = await vector_search(db, params.query, filter_conditions, filter_params, _CANDIDATE_LIMIT)

    bm25_norm = _normalize(bm25_raw)
    vector_norm = _normalize(vector_raw)

    all_ids = set(bm25_norm) | set(vector_norm)

    scored: dict[str, float] = {}
    for doc_id in all_ids:
        v = vector_norm.get(doc_id, 0.0)
        b = bm25_norm.get(doc_id, 0.0)
        meta = 1.0 if has_filters else 0.0
        scored[doc_id] = (
            params.vector_weight * v
            + params.bm25_weight * b
            + params.metadata_weight * meta
        )

    top_ids = sorted(scored, key=lambda x: scored[x], reverse=True)[: params.top_k]

    if not top_ids:
        return SearchResponse(query=params.query, total_results=0, results=[])

    top_uuids = [uuid.UUID(i) for i in top_ids]
    rows = await db.execute(
        text("""
            SELECT
                d.id, d.original_name, d.doc_type, d.source,
                d.retrieval_summary, d.parent_document_id,
                m.issuer, m.jurisdiction, m.facility_name,
                m.species, m.inspection_date, m.inspector_name,
                m.reference_number, m.categories, m.extra
            FROM documents d
            LEFT JOIN document_metadata m ON m.document_id = d.id
            WHERE d.id = ANY(:ids)
        """),
        {"ids": top_uuids},
    )
    doc_rows = {str(r[0]): r for r in rows.fetchall()}

    results: list[SearchResult] = []
    for doc_id in top_ids:
        r = doc_rows.get(doc_id)
        if not r:
            continue
        v_score = vector_norm.get(doc_id, 0.0)
        b_score = bm25_norm.get(doc_id, 0.0)
        meta_boost = 1.0 if has_filters else 0.0
        scores = ScoreBreakdown(
            vector_score=round(v_score, 4),
            bm25_score=round(b_score, 4),
            metadata_boost=round(meta_boost, 4),
            final_score=round(scored[doc_id], 4),
        )
        results.append(_build_result(r, scores))

    # Match reasoning is only meaningful when there's a query
    await annotate_with_reasoning(params.query, results, top_n=5)

    logger.info(
        "hybrid_search complete",
        extra={
            "query": params.query,
            "bm25_candidates": len(bm25_raw),
            "vector_candidates": len(vector_raw),
            "returned": len(results),
        },
    )

    return SearchResponse(
        query=params.query,
        total_results=len(results),
        results=results,
    )
