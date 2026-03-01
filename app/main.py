"""
app/main.py
-----------
FastAPI application entry point.

Endpoints:
    GET  /health          — liveness probe
    POST /chat            — session-based chatbot
    POST /quotes/draft    — quote drafting stub

Middleware:
    CORS: permissive by default (allow_origins=["*"])
    TODO (production): restrict allow_origins to known client domains.

React Native clients:
    Physical device:   http://<LAN_IP>:8000
    Android emulator:  http://10.0.2.2:8000
    iOS simulator:     http://localhost:8000
"""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import logging as app_logging
from app.chains import run_chain
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

logger = app_logging.logger

# ---------------------------------------------------------------------------
# LLM singleton — initialised once at startup
# ---------------------------------------------------------------------------
_llm = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm
    logger.info("startup: initialising LLM provider")
    _llm = get_llm()
    logger.info("startup: complete")
    yield
    logger.info("shutdown: complete")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Fair Play Initiative — Chatbot API",
    description="FastAPI backend for the Fair Play Initiative chatbot.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# TODO (production): replace allow_origins=["*"] with an explicit allowlist,
#   e.g. ["https://yourapp.example.com", "exp://192.168.1.x:19000"]
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    """Liveness probe — returns 200 + {"status": "ok"} if the server is up."""
    return HealthResponse(status="ok")


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
