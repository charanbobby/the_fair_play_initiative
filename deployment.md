# Deployment Guide

Two deployment targets:

| Target | What deploys | URL |
|--------|-------------|-----|
| **Hugging Face Spaces** | FastAPI backend (Docker runtime) | `https://<username>-<space-name>.hf.space` |
| **Docker (local/server)** | FastAPI backend (full LLM support) | `http://localhost:8000` |

> The Next.js frontend is deployed separately via its own CI/CD pipeline (auto-deploys on git push).

---

## Hugging Face Spaces Deployment (Recommended for Backend)

### How it works

- HF Spaces detects the SDK from the `README.md` YAML frontmatter (`sdk: docker`).
- It builds the **root `Dockerfile`** automatically on every push.
- The app is served on port **7860** (the HF Spaces default).
- No bundle size limit — full `requirements.txt` is installed.
- LangChain, LangGraph, and Arize tracing all work here with no bundle size constraints.

### Prerequisites

- [Hugging Face account](https://huggingface.co/join)
- `git` with Git LFS installed (`git lfs install`)
- HF Space created (see Step 1)

### Step 1 — Create a Hugging Face Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in:
   - **Space name**: e.g. `fair-play-backend`
   - **SDK**: `Docker`
   - **Visibility**: Public or Private
3. Click **Create Space**

### Step 2 — Add your HF Space as a remote

```bash
# Replace <username> and <space-name> with yours
git remote add hf https://huggingface.co/spaces/<username>/<space-name>
```

### Step 3 — Set environment variables in HF Spaces

In your Space dashboard → **Settings → Repository secrets**:

| Variable | Value | Notes |
|----------|-------|-------|
| `LLM_PROVIDER` | `mock` | Default; change to `openai` for real LLM |
| `OPENAI_API_KEY` | `sk-...` | Optional |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Optional |
| `ARIZE_API_KEY` | your key | Optional — enables tracing |
| `ARIZE_SPACE_ID` | your ID | Optional |

> Never commit keys to git — always use Secrets in the dashboard.

### Step 4 — Push to deploy

```bash
git push hf main
```

HF Spaces will automatically build the root `Dockerfile` and start the server. Build logs are visible in the Space dashboard.

### Step 5 — Verify

```bash
BASE=https://<username>-<space-name>.hf.space

curl $BASE/health
# → {"status":"ok"}

curl -X POST $BASE/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"hello","metadata":{}}'
# → {"reply":"MOCK_REPLY: hello","trace_id":"..."}

# Interactive API docs
open $BASE/docs
```

### HF Spaces notes

| Topic | Detail |
|-------|--------|
| Port | Must be `7860` (set in `Dockerfile` and `README.md` frontmatter) |
| Cold starts | Free tier spaces sleep after inactivity — first request may be slow |
| Persistent memory | Sessions reset on restart; use Redis for persistence |
| Hardware | Free CPU-basic → upgrade to GPU in Space settings for heavy inference |
| Logs | Available in Space dashboard → **Logs** tab |

---

## Docker Deployment (Local / Any VPS)

Use Docker for local development or deploying to Railway, Render, or Fly.io.

```bash
# Build (uses Dockerfile.backend — port 8000 for local dev)
docker build -f Dockerfile.backend -t fair-play-backend .

# Run mock mode
docker run --rm -p 8000:8000 fair-play-backend

# Run with real LLM
docker run --rm -p 8000:8000 \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  fair-play-backend

# Run with .env file
docker run --rm -p 8000:8000 --env-file .env fair-play-backend
```

### Deploy to Railway / Render / Fly.io

| Platform | Steps |
|----------|-------|
| **Railway** | Connect repo → select `Dockerfile.backend` → set env vars → deploy |
| **Render** | New Web Service → Docker → point to `Dockerfile.backend` |
| **Fly.io** | `fly launch --dockerfile Dockerfile.backend` |

---

## React Native — Base URL per Environment

| Environment | Base URL |
|-------------|----------|
| Physical device | `http://<LAN_IP>:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator | `http://localhost:8000` |
| HF Spaces (prod) | `https://<username>-<space-name>.hf.space` |

---

## Files Involved in Deployment

| File | Purpose |
|------|---------|
| `Dockerfile` | HF Spaces build (port 7860, non-root user) |
| `Dockerfile.backend` | Local Docker dev build (port 8000) |
| `requirements.txt` | Full Python deps (used by both Dockerfiles) |
| `README.md` | Contains HF Spaces YAML frontmatter (`sdk: docker`) |
| `.env` | Local secrets (never commit) |

---

## Helpful Links

- [HF Spaces Docker SDK docs](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [HF Spaces environment variables](https://huggingface.co/docs/hub/spaces-overview#managing-secrets)
- [uv documentation](https://docs.astral.sh/uv/)
