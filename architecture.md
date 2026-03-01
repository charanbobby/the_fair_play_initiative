# architecture.md
# Fair Play Initiative — Backend Architecture

---

## 1. Purpose and Scope

The Fair Play Initiative backend is a **Python FastAPI chatbot service** that:

- Accepts messages from any HTTP client (React Native app, web frontend, or curl)
- Maintains per-session conversation history in memory
- Delegates language generation to a pluggable LLM provider (default: mock)
- Exposes a quote drafting stub ready for future LLM wiring
- Runs as a single Docker container using **uv** for dependency management

This document describes the v0.1 architecture. It will evolve as LangGraph, RAG, and the scoring engine are added.

---

## 2. System Context

```
┌─────────────────────────────────────────┐
│           React Native Client           │
│  Physical: http://<LAN_IP>:8000         │
│  Android:  http://10.0.2.2:8000         │
│  iOS sim:  http://localhost:8000         │
└──────────────────┬──────────────────────┘
                   │  HTTP/JSON (CORS-enabled)
                   ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend (port 8000)     │
│                                         │
│  GET  /health                           │
│  POST /chat          ──► SessionMemory  │
│  POST /quotes/draft                     │
│                                         │
│  CORSMiddleware (allow_origins=["*"])   │
│  Global JSON error handler + trace_id  │
└──────────────────┬──────────────────────┘
                   │
          ┌────────▼────────┐
          │  LLM Provider   │
          │  mock (default) │
          │  openai         │
          │  anthropic      │
          └─────────────────┘
```

---

## 3. API Surface

| Method | Path             | Description                                     |
|--------|------------------|-------------------------------------------------|
| GET    | `/health`        | Liveness probe → `{"status": "ok"}`             |
| POST   | `/chat`          | Session chatbot → reply + trace_id + citations  |
| POST   | `/quotes/draft`  | Quote extraction stub → draft_quotes + notes    |

### `/chat` contract

**Request**
```json
{ "session_id": "string", "message": "string", "metadata": {} }
```

**Response**
```json
{
  "session_id": "string",
  "reply": "string",
  "trace_id": "<uuid4>",
  "citations": [],
  "debug": {}
}
```

### `/quotes/draft` contract

**Request**
```json
{ "input_text": "string", "style": "formal | neutral | informal" }
```

**Response**
```json
{ "draft_quotes": [], "notes": ["..."] }
```

---

## 4. Runtime Execution Flow

```
Client POST /chat
  │
  ├─ generate_trace_id()          → UUID4 per request
  ├─ log_request()                → structured log line
  ├─ session_memory.get_history() → prior turns for this session_id
  ├─ chains.build_messages()      → [system] + [history] + [human]
  ├─ llm.invoke(messages)         → mock: "MOCK_REPLY: <msg>"
  ├─ session_memory.append()      → saves human + ai turns
  ├─ log_response()
  └─ return ChatResponse(reply, trace_id, citations=[], debug={})
```

**Mock mode**: `LLM_PROVIDER=mock` (default). No credentials needed.
Chain returns `"MOCK_REPLY: <user_message>"` deterministically.

---

## 5. Key Modules and Responsibilities

| Module           | Responsibility |
|------------------|----------------|
| `app/main.py`    | FastAPI app factory, CORS middleware, all route handlers, global exception handler. Single entry point for uvicorn. |
| `app/config.py`  | Reads all env vars at import time with safe defaults. Single `settings` singleton shared across the app. |
| `app/schemas.py` | Pydantic v2 request/response models for all endpoints plus `ErrorResponse`. |
| `app/logging.py` | `generate_trace_id()`, `log_request()`, `log_response()`, `log_error()`. No-op safe OpenTelemetry stub. |
| `app/memory.py`  | Thread-safe in-memory session store (`dict` + `threading.Lock`). Singleton `session_memory`. |
| `app/llm.py`     | `get_llm()` factory returning `MockLLM`, `ChatOpenAI`, or `ChatAnthropic` based on `LLM_PROVIDER`. Graceful fallback to mock on missing credentials. |
| `app/chains.py`  | `build_messages()` assembles system + history + user message. `run_chain()` calls `llm.invoke()` and normalises the reply. TODO stubs for LangGraph and RAG. |
| `app/quotes.py`  | Deterministic stub for `/quotes/draft`. Returns empty lists; has TODO hooks for LLM-based extraction. |

---

## 6. Configuration and Secrets

All config is via environment variables. The app starts safely with **zero env vars set**.

| Variable             | Default  | Notes |
|----------------------|----------|-------|
| `LLM_PROVIDER`       | `mock`   | `mock`, `openai`, or `anthropic` |
| `LLM_MODEL`          | _(empty)_ | Falls back to provider default |
| `LLM_API_KEY`        | _(empty)_ | Generic key; provider-specific keys below take precedence |
| `OPENAI_API_KEY`     | _(empty)_ | Used when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY`  | _(empty)_ | Used when `LLM_PROVIDER=anthropic` |
| `OPENROUTER_API_KEY` | _(empty)_ | Future: OpenRouter gateway |
| `APP_HOST`           | `0.0.0.0` | Bind address |
| `APP_PORT`           | `8000`   | Bind port |
| `ARIZE_API_KEY`      | _(empty)_ | Enables Arize Phoenix tracing (no-op if absent) |
| `ARIZE_SPACE_ID`     | _(empty)_ | Arize workspace ID |

> **Never commit real secrets.** Use `.env` locally (git-ignored); inject vars at runtime in Docker or via your deployment platform's secrets manager.

---

## 7. React Native Integration Notes

### Base URL by environment

| Environment       | Base URL |
|-------------------|----------|
| Physical device   | `http://<LAN_IP_OF_DEV_MACHINE>:8000` |
| Android emulator  | `http://10.0.2.2:8000` |
| iOS simulator     | `http://localhost:8000` |

Find your LAN IP on macOS: `ipconfig getifaddr en0`  
Find your LAN IP on Windows: `ipconfig` → look for IPv4 under your Wi-Fi adapter

### CORS

The backend uses **permissive CORS** (`allow_origins=["*"]`) by default so React Native clients on any origin can reach it.

```
TODO (production): replace allow_origins=["*"] with an explicit allowlist.
```

### Example React Native fetch

```javascript
const BASE_URL = 'http://10.0.2.2:8000'; // Android emulator

const resp = await fetch(`${BASE_URL}/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: 'user-123',
    message: 'Hello!',
    metadata: {},
  }),
});
const data = await resp.json();
console.log(data.reply); // "MOCK_REPLY: Hello!"
```

---

## 8. Docker Design

**File:** `Dockerfile.backend`  
**Base image:** `python:3.11-slim` — minimal footprint, no build tools.

### Why uv?

- **10–100× faster** than pip for dependency resolution and installation
- Deterministic installs from `requirements.txt` (same as pip-compile output)
- Single binary; no venv overhead needed when using `--system`

### Why `--system`?

Inside Docker there is no active virtual environment. `uv pip install --system` installs directly into the system Python interpreter, which is the correct target for a containerised service.

### Installation sequence

```dockerfile
RUN pip install --no-cache-dir uv          # 1. Bootstrap uv itself
COPY requirements.txt .
RUN uv pip install --system --no-cache \   # 2. Install all deps via uv
    -r requirements.txt
```

### Startup command

```
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`uv run` ensures the correct Python environment is used for the process.

---

## 9. Observability / Tracing

- Every request generates a **`trace_id`** (UUID4) injected into logs and API responses.
- Structured logs use `level=… endpoint=… trace_id=…` format (stdout).
- `app/logging.py` attempts to initialise **Arize Phoenix + OpenTelemetry** on startup.
  - If `ARIZE_API_KEY` is absent → logs `"tracing=disabled"` and continues.
  - If SDK packages are missing → catches `ImportError`, logs a warning, continues.
- **No-op safe**: missing collector never crashes the server.

**Future extension:**
```python
# TODO: configure OTLP exporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
```

---

## 10. Planned Evolution

- **Redis session store** — replace in-memory `SessionMemory` for multi-instance deployments
- **LangGraph orchestration** — replace linear `run_chain()` with a stateful graph agent supporting branching and tool use
- **Retrieval Augmented Generation (RAG)** — add a retriever node (Chroma or Pinecone) to ground replies in policy documents
- **Attendance policy parsing** — ingest PDF policy documents via `langchain-community` PDF loaders; extract rules as structured data
- **Point scoring engine** — deterministic scoring module that computes point totals and flags threshold violations
- **Tool calling** — bind tools (web search via Tavily, calculator, policy lookup) to the LangGraph agent
- **Authentication** — add JWT middleware; tie session_id to authenticated user ID
- **Streaming replies** — switch `/chat` to `StreamingResponse` using LangGraph's `.stream()` for real-time output
- **OpenRouter gateway** — route LLM calls through OpenRouter for multi-model flexibility
