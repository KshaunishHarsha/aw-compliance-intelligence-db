"""
ASGI middleware to assign a request ID to every incoming request and surface
it in (a) every log line emitted during the request and (b) the response
header `X-Request-ID`. Clients can override by passing their own X-Request-ID
header, which is useful when an upstream proxy already assigned one.
"""
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logging import new_request_id, set_request_id

logger = logging.getLogger("http")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("x-request-id") or new_request_id()
        token = set_request_id(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": elapsed_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            set_request_id(None)
            # Reset the contextvar token in case the framework re-uses tasks
            try:
                token.var.reset(token)
            except Exception:
                pass
