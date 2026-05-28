from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embedder import embed
from app.retrieval.metadata_filter import where_clause


async def vector_search(
    db: AsyncSession,
    query: str,
    filter_conditions: list[str],
    filter_params: dict,
    limit: int = 100,
) -> dict[str, float]:
    """
    Semantic search using pgvector cosine similarity.
    Embeds the query with text-embedding-3-small, searches document-level embeddings.
    Returns {document_id_str: similarity_score} where score is in [0, 1].
    """
    query_vector = embed(query)
    vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

    w_clause = where_clause(filter_conditions)

    sql = text(f"""
        SELECT e.document_id::text,
               1 - (e.embedding <=> CAST(:query_vector AS vector)) AS score
        FROM embeddings e
        JOIN documents d ON d.id = e.document_id
        LEFT JOIN document_metadata m ON m.document_id = d.id
        WHERE e.chunk_id IS NULL
          {('AND ' + ' AND '.join(filter_conditions)) if filter_conditions else ''}
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {**filter_params, "query_vector": vector_str, "limit": limit})
    rows = result.fetchall()
    return {row[0]: float(row[1]) for row in rows}
