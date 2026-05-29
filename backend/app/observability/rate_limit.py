"""
Simple sliding-window rate limiter backed by Redis.

Used on /auth/login to slow down credential-stuffing attempts. The bucket key
is the client's IP address; if a proxy is in front we honor the first
X-Forwarded-For entry.
"""
from __future__ import annotations

import logging
import time

from fastapi import HTTPException, Request, status
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # Take the first IP in the chain
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(
    redis_client: aioredis.Redis,
    request: Request,
    bucket: str,
    limit_per_minute: int,
) -> None:
    """
    Sliding 60s window per (bucket, client IP). Raises 429 when exceeded.

    Uses a Redis sorted set; each request adds an entry timestamped at "now",
    we trim entries older than 60s, then count. O(1) amortized per request.
    """
    ip = _client_ip(request)
    key = f"rl:{bucket}:{ip}"
    now_ms = int(time.time() * 1000)
    window_start = now_ms - 60_000

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {f"{now_ms}-{request.url.path}": now_ms})
    pipe.zcard(key)
    pipe.expire(key, 120)
    _, _, count, _ = await pipe.execute()

    if count > limit_per_minute:
        logger.warning(
            "rate limit exceeded",
            extra={"bucket": bucket, "client_ip": ip, "count": count, "limit": limit_per_minute},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Try again in a minute.",
            headers={"Retry-After": "60"},
        )
