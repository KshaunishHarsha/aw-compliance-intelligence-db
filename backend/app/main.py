import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import auth, chat, documents, ingest, search, users
from app.config import get_settings
from app.db.session import async_engine
from app.observability.logging import configure_logging, get_request_id
from app.observability.middleware import RequestIDMiddleware

settings = get_settings()

# Structured JSON logs in production, human-readable in dev
configure_logging(
    level=settings.log_level,
    json_logs=settings.is_production,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "startup",
        extra={"environment": settings.environment, "cors_origins": settings.cors_origins_list},
    )
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Animal Welfare Compliance Intelligence Platform",
    lifespan=lifespan,
    # Hide docs in production (set DOCS_URL env var to override if needed)
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

# Order: RequestID first so every other middleware/handler sees the ID
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# ── Error handlers — consistent JSON shape ─────────────────────────────────

def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = {"error": {"code": code, "message": message}}
    rid = get_request_id()
    if rid:
        payload["error"]["request_id"] = rid
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return _error_response(
        exc.status_code,
        code=f"http_{exc.status_code}",
        message=str(exc.detail) if exc.detail else "Error",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    # Compact summary; full errors are in the logs
    logger.warning("validation error", extra={"errors": exc.errors()})
    return _error_response(
        422,
        code="validation_error",
        message="Request body or parameters are invalid.",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # In production, never leak stack traces to the client. In dev we still
    # want the error message visible for fast debugging.
    logger.exception("unhandled exception")
    detail = "Internal server error." if settings.is_production else f"{type(exc).__name__}: {exc}"
    return _error_response(500, code="internal_error", message=detail)


# ── Routes ────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


# ── Health probes ─────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    """Liveness — the process is up and serving HTTP."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/db")
async def health_db() -> dict:
    """Readiness — Postgres is reachable."""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error("db health failed", extra={"error": str(e)})
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)})


@app.get("/health/redis")
async def health_redis() -> dict:
    """Readiness — Redis is reachable."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        pong = await client.ping()
        return {"status": "ok", "pong": bool(pong)}
    except Exception as e:
        logger.error("redis health failed", extra={"error": str(e)})
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)})
    finally:
        await client.aclose()


@app.get("/health/storage")
async def health_storage() -> dict:
    """Readiness — Supabase Storage is configured (does not fetch a file)."""
    if not settings.supabase_url or not settings.supabase_key:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "Supabase credentials not configured"},
        )
    return {"status": "ok", "bucket": settings.supabase_bucket}
