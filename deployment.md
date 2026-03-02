# Deployment Guide

Quick reference for every deployment you'll run frequently while building this project.

---

## 1. Local Development (Fastest Iteration)

No Docker, hot-reload on every file save.

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Test it:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs       # Swagger UI
```

Requires: Python 3.11+, `uv` installed, `uv pip install --system -r requirements.txt` run once.

---

## 2. Local Docker (Matches HF Spaces Exactly)

Use this to catch Docker-specific issues before pushing to HF.

```bash
# Build (mirrors the HF Spaces Dockerfile — port 7860)
docker build -t fair-play-backend .

# Run
docker run --rm -p 7860:7860 fair-play-backend

# With a real LLM
docker run --rm -p 7860:7860 \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  fair-play-backend

# With .env file
docker run --rm -p 7860:7860 --env-file .env fair-play-backend
```

Test it:
```bash
curl http://localhost:7860/health
```

> **Tip**: Use `Dockerfile.backend` (port 8000) for a dev-friendly local build that doesn't require port 7860.
> ```bash
> docker build -f Dockerfile.backend -t fair-play-backend-dev .
> docker run --rm -p 8000:8000 fair-play-backend-dev
> ```

---

## 3. Hugging Face Spaces (Backend Production)

**Space URL**: https://huggingface.co/spaces/charanbobby/fair-play-backend
**Live API**: https://charanbobby-fair-play-backend.hf.space

HF builds the root `Dockerfile` automatically on every push.

```bash
# Push to HF (deploy backend)
git push hf master:main
```

Monitor the build in the **Logs** tab on the Space dashboard.

#### First-time setup (already done)
```bash
git remote add hf https://huggingface.co/spaces/charanbobby/fair-play-backend
```

#### Set secrets (HF dashboard → Settings → Repository secrets)

| Variable | Notes |
|----------|-------|
| `LLM_PROVIDER` | `mock` (default) or `openai` / `anthropic` |
| `OPENAI_API_KEY` | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Required if `LLM_PROVIDER=anthropic` |
| `ARIZE_API_KEY` | Optional — enables Phoenix tracing |
| `ARIZE_SPACE_ID` | Optional |

#### Verify live endpoints
```bash
BASE=https://charanbobby-fair-play-backend.hf.space

curl $BASE/health
curl -X POST $BASE/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"hello","metadata":{}}'
```

---

## 4. GitHub (Version Control)

Push to GitHub to keep the repo in sync. This does **not** trigger an HF build.

```bash
git push origin master
```

#### Push to both at once
```bash
git push origin master && git push hf master:main
```

---

## 5. Running Tests

Run before every push to catch regressions.

```bash
pytest tests/ -v
```

Expected passing tests:
- `test_health_endpoint`
- `test_chat_endpoint_mock`
- `test_chat_session_memory`
- `test_quotes_draft_stub`

---

## 6. Environment Variables Reference

| Variable | Local default | HF Spaces |
|----------|--------------|-----------|
| `LLM_PROVIDER` | `mock` | Set in Secrets |
| `LLM_API_KEY` | — | Set in Secrets |
| `OPENAI_API_KEY` | from `.env` | Set in Secrets |
| `ANTHROPIC_API_KEY` | from `.env` | Set in Secrets |
| `ARIZE_API_KEY` | from `.env` | Set in Secrets |
| `APP_PORT` | `8000` (local) | `7860` (HF) |

> Never commit `.env` to git. It is already in `.gitignore`.

---

## 7. Typical Dev Workflow

```
1. Edit code locally
2. pytest tests/ -v              ← catch issues fast
3. docker build -t fair-play-backend . && docker run --rm -p 7860:7860 fair-play-backend
                                 ← verify Docker works
4. git add . && git commit -m "..."
5. git push origin master        ← GitHub backup
6. git push hf master:main       ← HF Spaces deploy (live in ~1 min)
```

---

## 8. Future Deployment Targets (Planned)

| Target | When to use |
|--------|-------------|
| **Railway** | When you need a persistent server with Redis session memory |
| **Fly.io** | When you need multi-region or GPU inference |
| **Render** | Simple Docker hosting with free tier |
| **React Native app** | Point `BASE_URL` at the HF Space URL or LAN IP (see README) |
