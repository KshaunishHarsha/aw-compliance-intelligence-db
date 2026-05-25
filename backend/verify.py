import asyncio
from sqlalchemy import text
from app.db.session import async_engine
from app.tasks.ingestion import ping

async def verify():
    async with async_engine.connect() as conn:
        # Check pgvector
        res = await conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        vector_ext = res.fetchone()
        assert vector_ext is not None, "pgvector extension not found!"
        print("pgvector extension verified.")

        # Insert dummy doc and chunk to test FTS trigger
        await conn.execute(text("INSERT INTO documents (id, filename, original_name, file_path) VALUES ('00000000-0000-0000-0000-000000000001', 'test.pdf', 'test.pdf', '/test.pdf')"))
        await conn.execute(text("INSERT INTO chunks (id, document_id, chunk_index, chunk_type, raw_text, retrieval_summary) VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 1, 'finding', 'raw text content', 'summary content')"))
        await conn.commit()
        
        res2 = await conn.execute(text("SELECT fts_vector FROM chunks WHERE id = '00000000-0000-0000-0000-000000000002'"))
        fts = res2.scalar()
        assert fts is not None, "fts_vector is null!"
        assert 'content' in fts, f"fts_vector does not contain expected tokens: {fts}"
        print("FTS trigger verified.")

    # Check celery
    result = ping.delay().get(timeout=5)
    assert result == {"status": "pong"}, f"Celery task failed with: {result}"
    print("Celery ping verified.")

if __name__ == "__main__":
    asyncio.run(verify())
