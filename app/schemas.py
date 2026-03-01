"""
app/schemas.py
--------------
Pydantic v2 request/response models for all API endpoints.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
import uuid


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., description="User message text")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    citations: list[Any] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# /quotes/draft
# ---------------------------------------------------------------------------

class QuoteDraftRequest(BaseModel):
    input_text: str = Field(..., description="Raw text to extract/draft quotes from")
    style: str = Field(
        default="neutral",
        description="Quote style: 'formal' | 'neutral' | 'informal'",
    )


class QuoteDraftResponse(BaseModel):
    draft_quotes: list[Any] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error envelope (returned by global exception handler)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detail: dict[str, Any] = Field(default_factory=dict)
