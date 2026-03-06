"""
app/main.py
-----------
FastAPI application entry point.

Endpoints:
    GET  /health          — liveness probe
    GET  /                — serve the public landing page
    GET  /dashboard       — serve the FPI admin SPA (static HTML)
    POST /chat            — session-based chatbot
    POST /quotes/draft    — quote drafting stub

    /api/v1/regions       — Region CRUD
    /api/v1/organizations — Organization CRUD
    /api/v1/policies      — Policy CRUD
    /api/v1/rules         — Rule CRUD + toggle
    /api/v1/employees     — Employee CRUD + override
    /api/v1/attendance    — CSV upload + log listing
    /api/v1/alerts        — Alert listing
    /api/v1/dashboard     — Stats aggregation

Middleware:
    CORS: permissive by default (allow_origins=["*"])
    TODO (production): restrict allow_origins to known client domains.
"""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import logging as app_logging
from app.chains import run_chain
from app.database import engine, get_db, SessionLocal
from app import models
from app.llm import get_llm
from app.memory import session_memory
from app.quotes import draft_quotes
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    QuoteDraftRequest,
    QuoteDraftResponse,
    ErrorResponse,
)
from app.logging import generate_trace_id, log_request, log_response, log_error

# Routers
from app.routers import (
    regions,
    organizations,
    policies,
    rules,
    employees,
    attendance,
    alerts,
    dashboard,
    feedback,
    playground,
)

logger = app_logging.logger

# ---------------------------------------------------------------------------
# LLM singleton — initialised once at startup
# ---------------------------------------------------------------------------
_llm = None

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm
    try:
        logger.info("startup: creating database tables")
        models.Base.metadata.create_all(bind=engine)

        logger.info("startup: seeding database")
        from app.seed import seed
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("startup: database init failed (will retry on first request): %s", exc)

    logger.info("startup: initialising LLM provider")
    _llm = get_llm()
    logger.info("startup: complete")
    yield
    logger.info("shutdown: complete")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Apprentice — Fair Play Initiative API",
    description="FastAPI backend for Apprentice: verifiable agentic workflows. First domain: Fair Play Initiative (workforce attendance compliance).",
    version="0.9.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files (SPA)
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# FPI REST API routers
# ---------------------------------------------------------------------------
API_PREFIX = "/api/v1"

app.include_router(regions.router, prefix=API_PREFIX)
app.include_router(organizations.router, prefix=API_PREFIX)
app.include_router(policies.router, prefix=API_PREFIX)
app.include_router(rules.router, prefix=API_PREFIX)
app.include_router(employees.router, prefix=API_PREFIX)
app.include_router(attendance.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(feedback.router, prefix=API_PREFIX)
app.include_router(playground.router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Global exception handler — always returns JSON with a trace_id
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = generate_trace_id()
    log_error(str(request.url.path), trace_id, str(exc))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            trace_id=trace_id,
            detail={"traceback": traceback.format_exc()[-500:]},
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_landing():
    """Serve the public landing page, falling back to the SPA."""
    landing = STATIC_DIR / "landing.html"
    if landing.exists():
        return FileResponse(landing)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"message": "FPI API is running."},
        status_code=200,
    )


@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    """Serve the FPI admin SPA."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"message": "Dashboard not available. Place index.html in app/static/."},
        status_code=200,
    )


@app.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    """Liveness probe — returns 200 + {"status": "ok"} if the server is up."""
    from app.config import settings as _cfg
    return HealthResponse(status="ok", is_playground=_cfg.IS_PLAYGROUND)


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Session-based chatbot endpoint.

    Maintains per-session conversation history in memory.
    Uses the configured LLM provider (default: mock).
    """
    trace_id = generate_trace_id()
    log_request("/chat", trace_id, {"session_id": body.session_id})

    # Retrieve existing history
    history = session_memory.get_history(body.session_id)

    # Run the chain
    reply = run_chain(
        llm=_llm,
        history=history,
        user_message=body.message,
        trace_id=trace_id,
    )

    # Persist both turns to session memory
    session_memory.append(body.session_id, "human", body.message)
    session_memory.append(body.session_id, "ai", reply)

    log_response("/chat", trace_id)

    return ChatResponse(
        session_id=body.session_id,
        reply=reply,
        trace_id=trace_id,
        citations=[],
        debug={"provider": str(type(_llm).__name__)},
    )


@app.post("/quotes/draft", response_model=QuoteDraftResponse, tags=["quotes"])
async def quotes_draft(body: QuoteDraftRequest) -> QuoteDraftResponse:
    """
    Quote drafting stub.

    Accepts input text and style; returns empty draft_quotes for now.
    TODO: wire to LLM-based extraction when the feature is implemented.
    """
    trace_id = generate_trace_id()
    log_request("/quotes/draft", trace_id, {"style": body.style})

    result = draft_quotes(body.input_text, body.style)

    log_response("/quotes/draft", trace_id)

    return QuoteDraftResponse(
        draft_quotes=result["draft_quotes"],
        notes=result["notes"],
    )
