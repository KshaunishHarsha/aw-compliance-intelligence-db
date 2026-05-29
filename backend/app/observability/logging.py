"""
Structured JSON logging configuration.

Emits one JSON object per log record so logs in Railway / Vercel / any log
aggregator can be queried by field. A contextvar-based request_id is threaded
through every log line within a request via the LogContext filter so an entire
request's logs can be grouped by `request_id`.

In development (`environment != "production"`), falls back to human-readable
single-line output for easier reading in `docker compose logs`.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Any

# Per-request context propagated via contextvars (async-safe).
_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Standard LogRecord attrs we never want to duplicate in `extra`.
_RESERVED_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


def set_request_id(value: str | None) -> contextvars.Token:
    return _request_id_ctx.set(value)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


class JsonFormatter(logging.Formatter):
    """Render every record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = get_request_id()
        if rid:
            payload["request_id"] = rid

        # Surface any extra={} fields the caller passed
        for k, v in record.__dict__.items():
            if k in _RESERVED_ATTRS or k.startswith("_"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    """Compact one-line format for `docker compose logs` readability."""

    def format(self, record: logging.LogRecord) -> str:
        rid = get_request_id()
        rid_part = f" [{rid}]" if rid else ""
        # Surface any extra={} structured fields inline
        extras: list[str] = []
        for k, v in record.__dict__.items():
            if k in _RESERVED_ATTRS or k.startswith("_"):
                continue
            extras.append(f"{k}={v}")
        extras_part = (" " + " ".join(extras)) if extras else ""
        base = (
            f"{time.strftime('%H:%M:%S', time.gmtime(record.created))} "
            f"{record.levelname:5}{rid_part} {record.name}: "
            f"{record.getMessage()}{extras_part}"
        )
        if record.exc_info:
            base = base + "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(level: str, json_logs: bool) -> None:
    """Idempotently install the chosen formatter on the root logger."""
    formatter: logging.Formatter = JsonFormatter() if json_logs else HumanFormatter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level.upper())
    # Replace any existing handlers so the format applies cleanly
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers in production
    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel("WARNING")
