# architecture.md
# Fair Play Initiative — Backend Architecture

---

## 1. Purpose and Scope

The Fair Play Initiative is a **balanced attendance management platform** that:

- Tracks employee attendance violations using a configurable point system
- Manages multiple organisations and regions, each with their own policies and rules
- Processes attendance logs (CSV/Excel) and automatically scores violations
- Provides an admin dashboard with point trends, red flags, and manual overrides
- Includes a pluggable AI chatbot layer for policy Q&A and quote drafting

The backend is a **Python FastAPI service** with a SQLite (dev) / PostgreSQL (prod) database,
served as a single Docker container on **port 7860** (Hugging Face Spaces compatible).
The frontend (`app/static/index.html`) is a static single-page app served directly by FastAPI.

---

## 2. System Context

```
┌───────────────────────────────────────────────┐
│           Browser (Admin User)                │
│   http://localhost:7860                       │
│   static SPA — HTML + Tailwind + vanilla JS  │
└──────────────────────┬────────────────────────┘
                       │  HTTP/JSON (CORS-enabled)
                       ▼
┌───────────────────────────────────────────────┐
│        FastAPI Backend  (port 7860)           │
│                                               │
│  GET   /                   → SPA (index.html) │
│  GET   /health                                │
│  POST  /chat         ──► SessionMemory        │
│  POST  /quotes/draft                          │
│                                               │
│  /api/v1/regions         CRUD                 │
│  /api/v1/organizations   CRUD                 │
│  /api/v1/policies        CRUD                 │
│  /api/v1/rules           CRUD + toggle        │
│  /api/v1/employees       CRUD + override      │
│  /api/v1/attendance      upload / process     │
│  /api/v1/alerts          list                 │
│  /api/v1/dashboard/stats aggregation          │
│                                               │
│  CORSMiddleware (allow_origins=["*"])         │
│  Global JSON error handler + trace_id        │
└─────────┬──────────────────────┬─────────────┘
          │                      │
    ┌─────▼──────┐        ┌──────▼──────┐
    │  Database  │        │ LLM Provider│
    │  SQLite    │        │ mock (def.) │
    │  (fpi.db)  │        │ openai      │
    │  via SQLAl-│        │ anthropic   │
    │  chemy 2.0 │        └─────────────┘
    └────────────┘
```

---

## 3. Data Model

```
Region ─────────────────────────────────────────
  id          TEXT PK
  name        TEXT
  code        TEXT
  timezone    TEXT
  laborLaws   TEXT

Organization ───────────────────────────────────
  id          TEXT PK
  name        TEXT
  code        TEXT
  active      BOOL

OrganizationRegion (M2M join) ──────────────────
  organizationId  FK → Organization
  regionId        FK → Region

Policy ─────────────────────────────────────────
  id              TEXT PK
  name            TEXT
  organizationId  FK → Organization
  regionId        FK → Region
  active          BOOL
  effectiveDate   DATE

Rule ───────────────────────────────────────────
  id          INTEGER PK
  policyId    FK → Policy (nullable = global rule)
  name        TEXT
  condition   TEXT  (late | early | absence | no-call | ...)
  threshold   INTEGER  (minutes; 0 = any)
  points      REAL
  description TEXT
  active      BOOL

Employee ───────────────────────────────────────
  id              INTEGER PK
  firstName       TEXT
  lastName        TEXT
  email           TEXT UNIQUE
  department      TEXT
  position        TEXT
  startDate       DATE
  points          REAL   (rolling total)
  trend           TEXT   (up | down | stable)
  nextReset       DATE
  organizationId  FK → Organization
  regionId        FK → Region
  policyId        FK → Policy

PointHistory ───────────────────────────────────
  id          INTEGER PK
  employeeId  FK → Employee
  date        DATE
  type        TEXT   (violation name or "Manual Override: ...")
  points      REAL   (positive = penalty, negative = deduction)
  status      TEXT   (Active | Excused | Approved)
  reason      TEXT   (populated for overrides)

AttendanceLog ──────────────────────────────────
  id              INTEGER PK
  employeeId      FK → Employee
  organizationId  FK → Organization
  regionId        FK → Region
  policyId        FK → Policy
  date            DATE
  scheduledIn     TEXT
  scheduledOut    TEXT
  actualIn        TEXT
  actualOut       TEXT
  violation       TEXT   (nullable)
  points          REAL
  status          TEXT   (Compliant | Violation | Active)

Alert ──────────────────────────────────────────
  id              INTEGER PK
  organizationId  FK → Organization  (nullable = global)
  type            TEXT   (info | warning | danger | success)
  message         TEXT
  createdAt       DATETIME
```

---

## 4. REST API Surface

### Core / Infra

| Method | Path             | Description                                    |
|--------|------------------|------------------------------------------------|
| GET    | `/`              | Serve SPA (`app/static/index.html`)            |
| GET    | `/health`        | Liveness probe → `{"status": "ok"}`            |
| POST   | `/chat`          | Session chatbot → reply + trace_id + citations |
| POST   | `/quotes/draft`  | Quote extraction stub → draft_quotes + notes   |

### FPI REST API (`/api/v1`)

| Method | Path                                     | Description                          |
|--------|------------------------------------------|--------------------------------------|
| GET    | `/api/v1/regions`                        | List all regions                     |
| POST   | `/api/v1/regions`                        | Create region                        |
| GET    | `/api/v1/regions/{id}`                   | Get region by ID                     |
| PUT    | `/api/v1/regions/{id}`                   | Update region                        |
| DELETE | `/api/v1/regions/{id}`                   | Delete region                        |
| GET    | `/api/v1/organizations`                  | List orgs (filterable)               |
| POST   | `/api/v1/organizations`                  | Create org                           |
| GET    | `/api/v1/organizations/{id}`             | Get org with nested policies         |
| PUT    | `/api/v1/organizations/{id}`             | Update org                           |
| DELETE | `/api/v1/organizations/{id}`             | Delete org                           |
| GET    | `/api/v1/policies`                       | List policies (filter: org, region)  |
| POST   | `/api/v1/policies`                       | Create policy                        |
| GET    | `/api/v1/policies/{id}`                  | Get policy with rules                |
| PUT    | `/api/v1/policies/{id}`                  | Update policy                        |
| DELETE | `/api/v1/policies/{id}`                  | Delete policy                        |
| GET    | `/api/v1/rules`                          | List rules (filter: policyId)        |
| POST   | `/api/v1/rules`                          | Create rule                          |
| PUT    | `/api/v1/rules/{id}`                     | Update rule                          |
| PATCH  | `/api/v1/rules/{id}/toggle`              | Toggle active/inactive               |
| DELETE | `/api/v1/rules/{id}`                     | Delete rule                          |
| GET    | `/api/v1/employees`                      | List employees (filter: org, region) |
| POST   | `/api/v1/employees`                      | Create employee                      |
| GET    | `/api/v1/employees/{id}`                 | Get employee with point history      |
| PUT    | `/api/v1/employees/{id}`                 | Update employee                      |
| DELETE | `/api/v1/employees/{id}`                 | Delete employee                      |
| POST   | `/api/v1/employees/{id}/override`        | Manual point override / excuse       |
| GET    | `/api/v1/attendance`                     | List processed logs (filter: org)    |
| POST   | `/api/v1/attendance/upload`              | Upload CSV/Excel file                |
| POST   | `/api/v1/attendance/process`             | Process queued attendance files      |
| GET    | `/api/v1/alerts`                         | List alerts (filter: org)            |
| GET    | `/api/v1/dashboard/stats`               | Aggregate stats for dashboard cards  |

---

## 5. Module Map

```
the_fair_play_initiative/
│
├── app/
│   ├── main.py          FastAPI factory, lifespan, CORS, router registration
│   ├── config.py        Env-var settings singleton (DATABASE_URL, LLM_PROVIDER, …)
│   ├── database.py      SQLAlchemy engine + SessionLocal + Base
│   ├── models.py        ORM models (Region, Organization, Policy, Rule, Employee, …)
│   ├── schemas.py       Pydantic v2 request/response models for all endpoints
│   ├── seed.py          One-time seed: populates DB with demo orgs/employees/rules
│   ├── logging.py       trace_id helpers, structured logs, OpenTelemetry stub
│   ├── memory.py        In-memory SessionMemory for chatbot conversation history
│   ├── llm.py           LLM provider factory (mock / openai / anthropic)
│   ├── chains.py        LangChain chain builder (system + history + user message)
│   ├── quotes.py        Quote drafting stub
│   ├── static/
│   │   └── index.html   Frontend SPA (served by FastAPI StaticFiles)
│   └── routers/
│       ├── __init__.py
│       ├── regions.py
│       ├── organizations.py
│       ├── policies.py
│       ├── rules.py
│       ├── employees.py
│       ├── attendance.py
│       ├── alerts.py
│       └── dashboard.py
│
├── agents/
│   ├── tools.py         LangGraph tool stubs
│   └── workflows.py     LangGraph workflow stubs
│
├── tests/
│   ├── test_health.py   Smoke tests for /health, /chat, /quotes/draft
│   └── test_fpi_api.py  CRUD tests for all /api/v1/* endpoints
│
├── Dockerfile           HF Spaces entry point (port 7860, non-root user)
├── requirements.txt     All Python dependencies
└── architecture.md      This document
```

---

## 6. Key Modules — Responsibilities

| Module | Responsibility |
|---|---|
| `app/main.py` | App factory, CORS, lifespan (DB init + seed), router registration, global error handler |
| `app/config.py` | All env vars with safe defaults. Singleton `settings` shared across the app |
| `app/database.py` | SQLAlchemy `engine`, `SessionLocal`, `Base`, `get_db` dependency |
| `app/models.py` | All ORM table definitions. Relationships declared for easy eager loading |
| `app/schemas.py` | Pydantic v2 models: `*Create`, `*Update`, `*Response` for every entity + chat/quotes |
| `app/seed.py` | Idempotent seed — checks if data exists before inserting demo records |
| `app/routers/*.py` | One file per resource. Each file owns its CRUD handlers + dependency injection |
| `app/logging.py` | `generate_trace_id()`, structured log helpers, OpenTelemetry no-op stub |
| `app/memory.py` | Thread-safe in-memory session store for chatbot history (dict + Lock) |
| `app/llm.py` | `get_llm()` factory: mock / ChatOpenAI / ChatAnthropic with graceful fallback |
| `app/chains.py` | Builds `[system, …history, human]` message list, calls `llm.invoke()` |

---

## 7. Configuration and Secrets

All config is via environment variables. The app starts safely with **zero env vars set**.

| Variable             | Default                     | Notes |
|----------------------|-----------------------------|-------|
| `DATABASE_URL`       | `sqlite:///./fpi.db`        | Swap to `postgresql://…` for production |
| `LLM_PROVIDER`       | `mock`                      | `mock`, `openai`, or `anthropic` |
| `LLM_MODEL`          | _(empty)_                   | Falls back to provider default |
| `LLM_API_KEY`        | _(empty)_                   | Generic key; provider-specific keys below take precedence |
| `OPENAI_API_KEY`     | _(empty)_                   | Used when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY`  | _(empty)_                   | Used when `LLM_PROVIDER=anthropic` |
| `OPENROUTER_API_KEY` | _(empty)_                   | Future: OpenRouter gateway |
| `APP_HOST`           | `0.0.0.0`                   | Bind address |
| `APP_PORT`           | `7860`                      | HF Spaces default |
| `ARIZE_API_KEY`      | _(empty)_                   | Enables Arize Phoenix tracing (no-op if absent) |
| `ARIZE_SPACE_ID`     | _(empty)_                   | Arize workspace ID |

> **Never commit real secrets.** Use `.env` locally (git-ignored); inject vars at runtime in Docker or via your deployment platform's secrets manager.

---

## 8. Execution Flows

### SPA Load
```
Browser GET /
  └─ FastAPI StaticFiles → app/static/index.html
       └─ JS bootstrap:
            ├─ fetch GET /api/v1/organizations
            ├─ fetch GET /api/v1/regions
            ├─ fetch GET /api/v1/employees
            ├─ fetch GET /api/v1/dashboard/stats
            └─ render UI
```

### Attendance Upload + Processing
```
Browser POST /api/v1/attendance/upload  (multipart CSV)
  ├─ Save file to temp storage
  ├─ Parse rows (employee, date, scheduledIn/Out, actualIn/Out)
  ├─ For each row:
  │    ├─ look up employee policy rules
  │    ├─ compute tardiness / early departure / absence flags
  │    ├─ assign points per matching rule
  │    └─ write AttendanceLog + PointHistory rows
  ├─ Update employee.points totals
  ├─ Generate Alert if employee crosses 8-point threshold
  └─ Return processed record count + violation summary
```

### Manual Override
```
Browser POST /api/v1/employees/{id}/override
  body: { type: "excuse"|"reduce"|"reset", amount?, reason }
  ├─ excuse  → find latest Active PointHistory, mark Excused, deduct points
  ├─ reduce  → subtract amount from employee.points (floor 0)
  ├─ reset   → set employee.points = 0, mark all history Excused
  ├─ write audit PointHistory entry (type = "Manual Override: …")
  └─ return updated Employee
```

### Chatbot
```
Browser POST /chat  { session_id, message }
  ├─ session_memory.get_history(session_id)
  ├─ chains.build_messages([system] + history + [human])
  ├─ llm.invoke(messages)   (mock by default)
  ├─ session_memory.append(human turn + ai turn)
  └─ return ChatResponse { reply, trace_id, citations: [] }
```

---

## 9. Docker Design

**HF Spaces entry point:** `Dockerfile` (root)  
**Local dev entry point:** `Dockerfile.backend`  
**Base image:** `python:3.11-slim`  
**Package manager:** `uv` — 10–100× faster than pip, no venv needed with `--system`  
**Port:** `7860` (required by HF Spaces)  
**User:** non-root `appuser` (required by HF Spaces)

```dockerfile
RUN pip install --no-cache-dir uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
COPY app/ ./app/
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

The SQLite database file (`fpi.db`) is created inside the container on first startup and seeded automatically. For durable persistence across container restarts, mount a volume:
```
docker run --rm -p 7860:7860 -v $(pwd)/data:/home/appuser/app fair-play-backend
```

---

## 10. Observability / Tracing

- Every request generates a **`trace_id`** (UUID4) injected into logs and API responses.
- Structured logs use `level=… endpoint=… trace_id=…` format (stdout).
- `app/logging.py` initialises **Arize Phoenix + OpenTelemetry** if `ARIZE_API_KEY` is set; silently no-ops otherwise.

---

## 11. Planned Evolution

- **PostgreSQL** — swap `DATABASE_URL` for a durable hosted DB in production
- **Alembic migrations** — replace `create_all()` with a proper migration history
- **Redis session store** — replace in-memory `SessionMemory` for multi-instance chat
- **LangGraph orchestration** — replace linear `run_chain()` with a stateful agent supporting branching and tool use
- **RAG / Policy parsing** — ingest PDF policy documents, extract rules as structured `Rule` rows via LLM
- **Streaming replies** — switch `/chat` to `StreamingResponse` with LangGraph `.stream()`
- **Authentication** — JWT middleware; bind `session_id` to authenticated user ID
- **Scheduled resets** — cron job to zero out employee points at end of rolling period
- **OpenRouter gateway** — route LLM calls through OpenRouter for multi-model flexibility
