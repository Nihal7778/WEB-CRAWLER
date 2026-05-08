"""
Structured logging setup.

Uses stdlib logging with JSON formatting in production and human-readable
formatting in dev. Every log line includes service name, level, timestamp,
and any extra context passed via the `extra` kwarg.

Why not structlog? structlog is great but adds a dependency. Stdlib
logging with a custom JSON formatter covers 95% of the value with
zero new packages.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from app.config import LOG_FORMAT, LOG_LEVEL, SERVICE_NAME


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON for log aggregators."""

    # Standard LogRecord attributes we don't want duplicated in the JSON.
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Pull any extra fields the caller passed via `extra={...}`.
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value

        # Exception info — stringified to fit JSON.
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable output for local dev."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )


def configure_logging() -> None:
    """Set up root logger. Call once at application startup."""
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # Clear any handlers configured by parent (e.g. uvicorn's defaults).
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if LOG_FORMAT == "json" else ConsoleFormatter())
    root.addHandler(handler)

    # Quiet down noisy libraries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper. Use this instead of logging.getLogger()."""
    return logging.getLogger(name)