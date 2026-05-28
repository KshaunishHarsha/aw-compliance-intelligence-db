from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.metadata_filter import where_clause


async def bm25_search(
    db: AsyncSession,
    query: str,
    filter_conditions: list[str],
    filter_params: dict,
    limit: int = 100,
) -> dict[str, float]:
    """
    Full-text search using PostgreSQL tsvector/tsquery (BM25-style).
    fts_vector is built by a DB trigger: retrieval_summary (weight A) + raw_text (weight B).
    Returns {document_id_str: raw_score}.
    """
    w_clause = where_clause(filter_conditions)

    sql = text(f"""
        SELECT d.id::text, ts_rank_cd(d.fts_vector, query, 32) AS score
        FROM documents d
        LEFT JOIN document_metadata m ON m.document_id = d.id,
        websearch_to_tsquery('english', :query) query
        {w_clause}
          AND d.fts_vector @@ query
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {**filter_params, "query": query, "limit": limit})
    rows = result.fetchall()
    return {row[0]: float(row[1]) for row in rows}
