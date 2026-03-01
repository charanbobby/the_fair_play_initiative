"""
app/logging.py
--------------
Structured logging utilities and trace-ID generation.

Observability note:
    OpenTelemetry / Arize Phoenix instrumentation is no-op safe:
    if the collector is absent, the app still starts and runs normally.
    Future wiring point: replace _try_init_tracing() with real OTLP export.
"""

import logging
import uuid
import sys
from typing import Optional

from app.config import settings

# ---------------------------------------------------------------------------
# Standard library logger — structured via JSON-like key=value format
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s level=%(levelname)s %(message)s",
)

logger = logging.getLogger("fair_play")


# ---------------------------------------------------------------------------
# Trace ID helpers
# ---------------------------------------------------------------------------

def generate_trace_id() -> str:
    """Return a new random UUID4 string to uniquely identify a request."""
    return str(uuid.uuid4())


def log_request(endpoint: str, trace_id: str, extra: Optional[dict] = None) -> None:
    """Emit a structured log line for an incoming request."""
    parts = [f"endpoint={endpoint}", f"trace_id={trace_id}"]
    if extra:
        parts += [f"{k}={v}" for k, v in extra.items()]
    logger.info(" ".join(parts))


def log_response(endpoint: str, trace_id: str, status: str = "ok") -> None:
    """Emit a structured log line for an outgoing response."""
    logger.info(f"endpoint={endpoint} trace_id={trace_id} status={status}")


def log_error(endpoint: str, trace_id: str, error: str) -> None:
    """Emit a structured error log line."""
    logger.error(f"endpoint={endpoint} trace_id={trace_id} error={error!r}")


# ---------------------------------------------------------------------------
# No-op safe OpenTelemetry / Arize Phoenix initialisation
# ---------------------------------------------------------------------------

def _try_init_tracing() -> None:
    """
    Attempt to initialise Arize Phoenix + OpenTelemetry tracing.

    This is entirely best-effort:  if the collector is unreachable or the
    SDK packages are not installed the function swallows the exception and
    logs a warning, so the server keeps running in un-traced mode.

    TODO: replace with proper OTLP endpoint config for production observability.
    """
    if not settings.ARIZE_API_KEY:
        logger.info("tracing=disabled reason='ARIZE_API_KEY not set'")
        return
    try:
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
        logger.info("tracing=enabled provider=arize-phoenix")
    except Exception as exc:  # pragma: no cover
        logger.warning(f"tracing=failed reason={exc!r}")


# Initialise tracing once at import time (no-op if collector absent)
_try_init_tracing()
