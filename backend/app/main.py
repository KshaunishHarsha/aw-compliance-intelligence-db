import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db.session import async_engine

settings = get_settings()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=settings.log_level
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    yield
    logger.info("Application shutdown")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(documents.router, prefix="/api/documents")
# app.include_router(search.router, prefix="/api/search")
# app.include_router(chat.router, prefix="/api/chat")

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}

@app.get("/health/db")
async def health_db():
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "detail": str(e)}
