---
title: Fair Play Initiative Backend
emoji: ⚖️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Fair Play Initiative

A student-athlete attendance tracking and advocacy platform combining a **Next.js frontend** and a **FastAPI chatbot backend**.


---

## Repository Structure

```
the_fair_play_initiative/
├── app/                    # Next.js app directory (TSX routes) + Python backend modules
│   ├── layout.tsx          # Next.js root layout
│   ├── page.tsx            # Next.js home page
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Env var config
│   ├── schemas.py          # Pydantic models
│   ├── logging.py          # Structured logging + trace IDs
│   ├── memory.py           # In-memory session store
│   ├── llm.py              # LLM provider abstraction
│   ├── chains.py           # LangChain chain builder
│   └── quotes.py           # Quote drafting stub
├── tests/                  # Pytest test suite
├── Dockerfile.backend      # Python/FastAPI Docker image (uv-based)
├── Dockerfile.build-test   # Node.js Next.js build test image
├── architecture.md         # System architecture documentation
├── requirements.txt        # Python dependencies (source of truth)
└── package.json            # Node.js dependencies
```

---

## Backend API

| Method | Endpoint        | Description                        |
|--------|-----------------|------------------------------------|
| GET    | `/health`       | Liveness probe                     |
| POST   | `/chat`         | Session-based chatbot              |
| POST   | `/quotes/draft` | Quote drafting stub                |

Full API contract: see [`architecture.md`](./architecture.md)

---

## Running the Backend

### Option A — Docker (recommended)

```bash
# Build the backend image
docker build -f Dockerfile.backend -t fair-play-backend .

# Run in mock mode (no API keys required)
docker run --rm -p 8000:8000 fair-play-backend

# Run with a real LLM
docker run --rm -p 8000:8000 \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  fair-play-backend
```

### Option B — Local (requires Python 3.11+ and uv)

```bash
# Install dependencies
uv pip install --system -r requirements.txt

# Start the server
uv run uvicorn app.main:app --reload --port 8000
```

---

## Configuration

Copy `.env` and fill in your keys (all optional — app runs in mock mode with no keys):

| Variable           | Default | Description |
|--------------------|---------|-------------|
| `LLM_PROVIDER`     | `mock`  | `mock`, `openai`, or `anthropic` |
| `LLM_API_KEY`      | —       | Generic API key |
| `OPENAI_API_KEY`   | —       | OpenAI key (when provider=openai) |
| `ANTHROPIC_API_KEY`| —       | Anthropic key (when provider=anthropic) |

---

## Tests

```bash
pytest tests/ -v
```

---

## React Native — Base URL Guide

When connecting a React Native app to this backend, use the appropriate base URL for your environment:

| Environment            | Base URL |
|------------------------|----------|
| **Physical device**    | `http://<LAN_IP_OF_DEV_MACHINE>:8000` |
| **Android emulator**   | `http://10.0.2.2:8000` |
| **iOS simulator**      | `http://localhost:8000` |

### Finding your LAN IP

- **macOS / Linux:** `ifconfig` → look for `inet` under `en0` (or `wlan0`)
- **Windows:** `ipconfig` → `IPv4 Address` under your Wi-Fi adapter

### Example fetch call

```javascript
const BASE_URL = 'http://10.0.2.2:8000'; // Android emulator

const resp = await fetch(`${BASE_URL}/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: 'user-session-1',
    message: 'Hello!',
    metadata: {},
  }),
});
const { reply, trace_id } = await resp.json();
```

> **CORS**: The backend allows all origins by default (`allow_origins=["*"]`).  
> Restrict this in production to your app's domain.

---

## Architecture

See [`architecture.md`](./architecture.md) for the full system design, module responsibilities, observability notes, and roadmap.
