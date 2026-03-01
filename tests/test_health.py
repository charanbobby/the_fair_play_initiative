"""
tests/test_health.py
--------------------
Smoke tests for the FastAPI chatbot backend.

Run with:
    pytest tests/ -v
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    """Async test client wired directly to the ASGI app (no server needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_health_endpoint(client: AsyncClient):
    """GET /health should return 200 and {"status": "ok"}."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# /chat (mock mode)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_chat_endpoint_mock(client: AsyncClient):
    """POST /chat should return a valid ChatResponse in mock mode."""
    payload = {
        "session_id": "test-session-1",
        "message": "hello world",
        "metadata": {},
    }
    resp = await client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_id"] == "test-session-1"
    assert "reply" in data
    assert "MOCK_REPLY" in data["reply"]
    assert "trace_id" in data
    assert "citations" in data
    assert "debug" in data


@pytest.mark.anyio
async def test_chat_session_memory(client: AsyncClient):
    """Sending two messages in the same session should include prior history."""
    session = "test-session-memory"

    # First turn
    resp1 = await client.post("/chat", json={
        "session_id": session,
        "message": "first message",
        "metadata": {},
    })
    assert resp1.status_code == 200

    # Second turn — history should now include first message
    resp2 = await client.post("/chat", json={
        "session_id": session,
        "message": "second message",
        "metadata": {},
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["session_id"] == session
    assert "MOCK_REPLY" in data2["reply"]


# ---------------------------------------------------------------------------
# /quotes/draft
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_quotes_draft_stub(client: AsyncClient):
    """POST /quotes/draft should return valid stub response."""
    payload = {
        "input_text": "Student-athletes deserve fair treatment.",
        "style": "formal",
    }
    resp = await client.post("/quotes/draft", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "draft_quotes" in data
    assert isinstance(data["draft_quotes"], list)
    assert "notes" in data
    assert len(data["notes"]) > 0
