import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.bm25 import bm25_search
from app.retrieval.metadata_filter import build_filter_conditions
from app.retrieval.reasoning import annotate_with_reasoning
from app.retrieval.vector import vector_search
from app.schemas.search import ScoreBreakdown, SearchResult, SearchResponse, SearchResultMetadata

logger = logging.getLogger(__name__)

_CANDIDATE_LIMIT = 100  # candidates fetched from each search before merging


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


async def hybrid_search(db: AsyncSession, params: Any) -> SearchResponse:
    filter_conditions, filter_params = build_filter_conditions(params)

    # BM25 and vector searches run sequentially — AsyncSession doesn't support concurrent ops
    bm25_raw = await bm25_search(db, params.query, filter_conditions, filter_params, _CANDIDATE_LIMIT)
    vector_raw = await vector_search(db, params.query, filter_conditions, filter_params, _CANDIDATE_LIMIT)

    bm25_norm = _normalize(bm25_raw)
    vector_norm = _normalize(vector_raw)

    # Determine which doc IDs matched metadata filters (for boost)
    # Any doc appearing in either result set passed the filter conditions
    all_ids = set(bm25_norm) | set(vector_norm)
    has_metadata_filter = bool(
        params.jurisdiction or params.facility_name or params.species or
        params.categories or params.date_from or params.date_to or
        params.inspector_name or params.reference_number or
        params.doc_type or params.source
    )

    scored: dict[str, float] = {}
    for doc_id in all_ids:
        v = vector_norm.get(doc_id, 0.0)
        b = bm25_norm.get(doc_id, 0.0)
        # metadata_boost: 1.0 if filters were applied and doc passed them (it's in the set)
        meta = 1.0 if has_metadata_filter else 0.0
        scored[doc_id] = (
            params.vector_weight * v
            + params.bm25_weight * b
            + params.metadata_weight * meta
        )

    top_ids = sorted(scored, key=lambda x: scored[x], reverse=True)[: params.top_k]

    if not top_ids:
        return SearchResponse(query=params.query, total_results=0, results=[])

    # Fetch full document + metadata for top results in one query
    import uuid as _uuid
    top_uuids = [_uuid.UUID(i) for i in top_ids]
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
        meta_boost = 1.0 if has_metadata_filter else 0.0

        results.append(SearchResult(
            id=r[0],
            original_name=r[1],
            doc_type=r[2],
            source=r[3],
            retrieval_summary=r[4],
            parent_document_id=r[5],
            metadata=SearchResultMetadata(
                issuer=r[6],
                jurisdiction=r[7],
                facility_name=r[8],
                species=r[9],
                inspection_date=r[10],
                inspector_name=r[11],
                reference_number=r[12],
                categories=r[13],
                extra=r[14],
            ),
            scores=ScoreBreakdown(
                vector_score=round(v_score, 4),
                bm25_score=round(b_score, 4),
                metadata_boost=round(meta_boost, 4),
                final_score=round(scored[doc_id], 4),
            ),
        ))

    # Generate match reasoning for top 5 results (LLM call, parallelized)
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
