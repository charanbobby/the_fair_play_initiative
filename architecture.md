# Fair Play Initiative — System Architecture

> **Version:** 0.3.0 — Covers the full FPI backend including database layer, REST API, SPA serving,
> Docker deployment, AI chatbot integration, and the new Policy Analyzer pipeline.

---

## 1. Purpose and Scope

The Fair Play Initiative (FPI) is a **balanced attendance management platform** built for HR
administrators managing multi-organization, multi-region workforces. Core capabilities:

| Capability | Detail |
|---|---|
| **Point-based violation tracking** | Each attendance infraction earns a configurable point value per policy rule (e.g., arriving >7 min late = 0.5 pts). Points accumulate on a rolling window and reset on a schedule. |
| **Multi-org / multi-region** | An unlimited number of organizations can be managed simultaneously. Each org links to one or more geographic regions. Policies (and their rules) are scoped per org + region pair. |
| **Automated CSV processing** | Admins upload a CSV of clock-in/clock-out records. The backend scores each row against the relevant employee's policy rules, writes `AttendanceLog` and `PointHistory` rows, and auto-generates alerts when an employee crosses the 8-point red-flag threshold. |
| **Manual oversight** | Supervisors can excuse violations, reduce totals by an arbitrary amount, or fully reset an employee's point count. Every override writes an audit trail entry to `PointHistory`. |
| **AI chatbot** | A pluggable LLM chatbot (mock by default; wires to OpenAI or Anthropic via env var) answers policy questions with per-session conversation memory. |
| **Policy document analysis** | Upload a PDF, DOCX, or TXT policy document. A 2-node LangGraph pipeline (keyword extraction → SQL ingestion plan) returns structured data mapped to the FPI schema — no database writes. Results are displayed inline on the Policy Management screen. |
| **Quote drafting stub** | A future-facing endpoint that will extract actionable quotes from uploaded policy documents. Currently returns an empty list with TODO hooks for LLM extraction. |

The system ships as a **single Docker container** (port 7860, Hugging Face Spaces compatible).
The React-style SPA frontend is compiled into `app/static/index.html` and served directly by
FastAPI — no separate web server or CDN needed.

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| API framework | FastAPI 0.115+ | Async, automatic OpenAPI docs, Pydantic validation |
| ORM | SQLAlchemy 2.0 (mapped columns) | Type-safe, supports both SQLite and PostgreSQL via `DATABASE_URL` |
| Database (dev/staging) | SQLite | Zero-config, persisted via a Docker named volume (`db_data`) |
| Database (production) | PostgreSQL (swap `DATABASE_URL`) | Replaces SQLite with no code changes |
| Package manager | `uv` | 10–100× faster than pip; installs into system Python with `--system` |
| Runtime | `uvicorn[standard]` | ASGI server; production-grade with async worker support |
| AI/LLM | LangChain + LangGraph + configurable provider | Mock → OpenAI → Anthropic via `LLM_PROVIDER` env var. Policy analyzer uses ChatOpenAI via OpenRouter. |
| Validation | Pydantic v2 | Co-located schemas; `model_config = {"from_attributes": True}` for ORM serialization |
| Frontend | Vanilla JS + Tailwind CSS + Chart.js + Lucide | Served as a static file; no build step required |
| Container runtime | Docker + Docker Compose | `data/` volume for SQLite persistence; non-root `appuser` |
| Deployment target | Hugging Face Spaces (Docker SDK) | Port 7860 required; non-root user required |

---

## 3. System Context

```
┌────────────────────────────────────────────────────────────┐
│                  Browser — Admin User                      │
│  http://localhost:7860   (or HF Spaces URL)               │
│                                                            │
│  HTML/CSS/JS SPA (index.html, Tailwind, Chart.js, Lucide) │
│  ┌─────────────── JS App Bootstrap ──────────────────┐    │
│  │  await Promise.all([                              │    │
│  │    fetch(/api/v1/organizations),                  │    │
│  │    fetch(/api/v1/regions),                        │    │
│  │    fetch(/api/v1/employees),                      │    │
│  │    fetch(/api/v1/attendance),                     │    │
│  │    fetch(/api/v1/alerts),                         │    │
│  │  ]) → render UI from API data                     │    │
│  └───────────────────────────────────────────────────┘    │
└───────────────────────────┬────────────────────────────────┘
                            │  HTTP / JSON  (CORS *)
                            ▼
┌────────────────────────────────────────────────────────────┐
│              FastAPI Application  (port 7860)              │
│                                                            │
│  GET  /              → FileResponse(app/static/index.html) │
│  GET  /health        → {"status":"ok"}                     │
│  POST /chat          → session chatbot (LangChain)         │
│  POST /quotes/draft  → quote extraction stub               │
│                                                            │
│  ┌──────────────── /api/v1 Routers ─────────────────────┐ │
│  │  regions · organizations · policies · rules          │ │
│  │  employees · attendance · alerts · dashboard         │ │
│  │  policies/analyze ← LangGraph pipeline              │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  Middleware: CORSMiddleware (allow_origins=["*"])          │
│  Global exception handler → JSON ErrorResponse + trace_id │
│  Lifespan hook: create_all() → seed() on first startup    │
└──────────┬──────────────────────────────┬──────────────────┘
           │                              │
     ┌─────▼───────┐             ┌────────▼────────┐
     │  SQLite DB  │             │   LLM Provider  │
     │  fpi.db     │             │   mock (default)│
     │  /data/     │             │   openai        │
     │  (volume)   │             │   anthropic     │
     └─────────────┘             └─────────────────┘
                                          │
                                 ┌────────▼────────────┐
                                 │  OpenRouter API     │
                                 │  (OPENROUTER_API_KEY│
                                 │  gpt-4o-mini or     │
                                 │  LLM_MODEL setting) │
                                 │  Policy Analyzer    │
                                 │  only               │
                                 └─────────────────────┘
```

---

## 4. Data Model

### Entity Relationship Summary

```
Region ◄────────────── OrganizationRegion (M2M) ──────────────► Organization
  │                                                                    │
  │ (regionId FK)                                            (organizationId FK)
  ▼                                                                    ▼
Policy ──────────────────────────────────────────────────────► Policy
  │ (policyId FK)
  ▼
Rule  (policyId nullable → global rule applies to all policies)

Employee → Organization (organizationId FK)
Employee → Region       (regionId FK)
Employee → Policy       (policyId FK)
Employee ◄──── PointHistory (employeeId FK)
Employee ◄──── AttendanceLog (employeeId FK)
Organization ◄── Alert (organizationId FK, nullable = platform-wide)
```

### Column Detail

**`Region`** — Geographic locale with labor law context

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | Slug (e.g. `us-west`) |
| `name` | TEXT | Display name |
| `code` | TEXT | Short code (e.g. `US-W`) |
| `timezone` | TEXT | IANA timezone string |
| `labor_laws` | TEXT | Free text e.g. "California Labor Code" |

**`Organization`** — A company or business unit

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | Slug (e.g. `org-1`) |
| `name` | TEXT | |
| `code` | TEXT | Short code used in employee email generation |
| `active` | BOOL | Soft disable without deleting |

**`OrganizationRegion`** — M2M join table (no extra columns)

**`Policy`** — Named ruleset scoped to an org+region pair

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | Slug (e.g. `pol-1`) |
| `name` | TEXT | |
| `organization_id` | FK → Organization | |
| `region_id` | FK → Region | |
| `active` | BOOL | Inactive policies are not applied during scoring |
| `effective_date` | DATE | When this version took effect |

**`Rule`** — A single scoreable violation criterion

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `policy_id` | FK → Policy (nullable) | NULL = global rule; applied when employee has no policy |
| `name` | TEXT | Human label (e.g. "Tardiness (> 7 min)") |
| `condition` | TEXT | `late` \| `early` \| `absence` \| `no-call` |
| `threshold` | INTEGER | Minutes. `0` = any deviation triggers the rule |
| `points` | REAL | Points added per violation (can be fractional) |
| `description` | TEXT | |
| `active` | BOOL | Inactive rules are skipped during scoring |

**`Employee`** — A tracked individual

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `first_name`, `last_name` | TEXT | |
| `email` | TEXT UNIQUE | Login identity (future auth) |
| `department` | TEXT | |
| `position` | TEXT | |
| `start_date` | DATE | |
| `points` | REAL | Rolling accumulated total |
| `trend` | TEXT | `up` \| `down` \| `stable` — manually maintained |
| `next_reset` | DATE | When rolling window resets |
| `organization_id` | FK → Organization | |
| `region_id` | FK → Region | |
| `policy_id` | FK → Policy (nullable) | NULL = global rules apply |

**`PointHistory`** — Immutable ledger of every point change

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `employee_id` | FK → Employee | |
| `date` | DATE | Infraction or override date |
| `type` | TEXT | Violation name OR `"Manual Override: excuse"` etc. |
| `points` | REAL | Positive = penalty added. Negative = points deducted. |
| `status` | TEXT | `Active` \| `Excused` \| `Approved` |
| `reason` | TEXT (nullable) | Filled for overrides |

**`AttendanceLog`** — One processed clock-in/out record per employee per day

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `employee_id` | FK → Employee | |
| `organization_id` | FK → Organization | Denormalized for fast filtering |
| `region_id` | FK → Region | Denormalized |
| `policy_id` | FK → Policy (nullable) | Denormalized |
| `date` | DATE | |
| `scheduled_in` / `scheduled_out` | TEXT | "09:00 AM" format |
| `actual_in` / `actual_out` | TEXT | Empty string means absent or not recorded |
| `violation` | TEXT (nullable) | Rule name if violated; NULL if compliant |
| `points` | REAL | Points assigned. 0 if compliant. |
| `status` | TEXT | `Compliant` \| `Violation` \| `Active` |

**`Alert`** — System or admin-generated notifications

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `organization_id` | FK → Organization (nullable) | NULL = platform-wide alert |
| `type` | TEXT | `info` \| `warning` \| `danger` \| `success` |
| `message` | TEXT | |
| `created_at` | DATETIME | `server_default=func.now()` |

---

## 5. REST API — Full Reference

### Core / Infrastructure

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | None | Serves `app/static/index.html`. Falls back to JSON hint if file missing. |
| `GET` | `/health` | None | Returns `{"status":"ok"}`. Used as liveness probe. |
| `POST` | `/chat` | None | Session chatbot. Maintains per-`session_id` history in RAM. |
| `POST` | `/quotes/draft` | None | Quote extraction stub. Returns empty list + notes. |

#### `/chat` — Request / Response

```json
// POST /chat
{
  "session_id": "user-abc-123",
  "message": "What happens at 8 points?",
  "metadata": {}
}

// 200 OK
{
  "session_id": "user-abc-123",
  "reply": "MOCK_REPLY: What happens at 8 points?",
  "trace_id": "e3b2c14a-...",
  "citations": [],
  "debug": { "provider": "MockLLM" }
}
```

#### `/quotes/draft` — Request / Response

```json
// POST /quotes/draft
{ "input_text": "Employees arriving...", "style": "formal" }

// 200 OK
{ "draft_quotes": [], "notes": ["Stub — LLM wiring TODO"] }
```

---

### FPI Data API (`/api/v1`)

#### Regions

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/regions` | — | 200 |
| `POST` | `/api/v1/regions` | — | 201, 400 (duplicate id) |
| `GET` | `/api/v1/regions/{id}` | — | 200, 404 |
| `PUT` | `/api/v1/regions/{id}` | — | 200, 404 |
| `DELETE` | `/api/v1/regions/{id}` | — | 204, 404 |

```json
// POST /api/v1/regions — body (RegionCreate)
{
  "id": "us-west",
  "name": "US West",
  "code": "US-W",
  "timezone": "America/Los_Angeles",
  "labor_laws": "California Labor Code"
}

// GET /api/v1/regions — response (RegionResponse[])
[{ "id": "us-west", "name": "US West", "code": "US-W",
   "timezone": "America/Los_Angeles", "labor_laws": "California Labor Code" }]
```

#### Organizations

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/organizations` | `active_only=true/false` | 200 |
| `POST` | `/api/v1/organizations` | — | 201, 400 |
| `GET` | `/api/v1/organizations/{id}` | — | 200, 404 |
| `PUT` | `/api/v1/organizations/{id}` | — | 200, 404 |
| `DELETE` | `/api/v1/organizations/{id}` | — | 204, 404 |

```json
// POST /api/v1/organizations
{
  "id": "org-1", "name": "TechCorp Industries",
  "code": "TCORP", "active": true,
  "region_ids": ["us-west", "us-east"]
}

// GET /api/v1/organizations — response
[{ "id": "org-1", "name": "TechCorp Industries", "code": "TCORP",
   "active": true, "region_ids": ["us-west", "us-east"] }]
```

#### Policies

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/policies` | `organization_id`, `region_id` | 200 |
| `POST` | `/api/v1/policies` | — | 201, 400 |
| `GET` | `/api/v1/policies/{id}` | — | 200, 404 — **includes nested `rules[]`** |
| `PUT` | `/api/v1/policies/{id}` | — | 200, 404 |
| `DELETE` | `/api/v1/policies/{id}` | — | 204, 404 — **cascades delete to rules** |
| `POST` | `/api/v1/policies/analyze` | — | 200, 400, 503 — **policy document analysis (no DB writes)** |

**`POST /api/v1/policies/analyze`** — Upload a policy document and receive structured analysis:

```text
Request: multipart/form-data — field "file" (PDF / DOCX / TXT)

Response 200 — PolicyAnalysisResponse:
{
  "filename": "hr-attendance-policy.pdf",
  "keywords": {
    "policy":               ["attendance policy", "effective date", "…"],
    "organization":         ["Acme Corp", "…"],
    "region":               ["California", "US-West", "…"],
    "rule":                 ["late arrival (>7 min)", "no-call absence", "…"],
    "attendance_log":       ["violation type", "…"],
    "point_history":        ["accrual", "rolling window", "…"],
    "alert":                ["red flag", "suspension trigger", "…"],
    "other_relevant_terms": ["progressive discipline", "…"],
    "confidence_score": 0.92
  },
  "sql_plan": {
    "objective": "Insert organization, region, policy, and rule rows for this document.",
    "tables_required": [
      { "table": "organization", "alias": "o", "purpose": "employer entity" },
      …
    ],
    "joins": [ { "left": "policy", "right": "organization", "condition": "policy.organization_id = organization.id", "join_type": "INNER" }, … ],
    "where_filters": [ { "description": "org exists check", "expression": "organization.name = 'Acme Corp'", "source_keyword": "Acme Corp" }, … ],
    "uses_cte": false,
    "cte_description": "organization.name = 'Acme Corp', region.code = 'US-W', …",
    "confidence_score": 0.88
  }
}

Response 400 — Unsupported file type or empty file
Response 503 — OPENROUTER_API_KEY not configured
Response 500 — LLM or pipeline error
```

No database writes are performed. The response is display-only for admin review.

#### Rules

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/rules` | `policy_id`, `active_only` | 200 |
| `POST` | `/api/v1/rules` | — | 201 |
| `GET` | `/api/v1/rules/{id}` | — | 200, 404 |
| `PUT` | `/api/v1/rules/{id}` | — | 200, 404 |
| `PATCH` | `/api/v1/rules/{id}/toggle` | — | 200, 404 — flips `active` bool |
| `DELETE` | `/api/v1/rules/{id}` | — | 204, 404 |

#### Employees

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/employees` | `organization_id`, `region_id`, `search` | 200 |
| `POST` | `/api/v1/employees` | — | 201, 400 (dup email) |
| `GET` | `/api/v1/employees/{id}` | — | 200, 404 — **includes nested `point_history[]`** |
| `PUT` | `/api/v1/employees/{id}` | — | 200, 404 |
| `DELETE` | `/api/v1/employees/{id}` | — | 204, 404 — **cascades delete to history + logs** |
| `GET` | `/api/v1/employees/{id}/history` | — | 200, 404 — point history only |
| `POST` | `/api/v1/employees/{id}/override` | — | 200, 400, 404 |

```json
// POST /api/v1/employees/{id}/override
{ "type": "excuse", "reason": "Medical emergency" }
{ "type": "reduce", "amount": 1.5, "reason": "Manager approved" }
{ "type": "reset",  "reason": "Annual policy reset" }

// All three return updated EmployeeDetailResponse with refreshed history
```

#### Attendance

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/attendance` | `organization_id`, `region_id`, `limit` | 200 |
| `POST` | `/api/v1/attendance/upload` | — | 200, 400 (non-CSV) |
| `POST` | `/api/v1/attendance/process` | — | 200 (stub) |

**CSV upload format** (`multipart/form-data`, field name: `file`):

```csv
employee_id,date,scheduled_in,scheduled_out,actual_in,actual_out
1,2026-03-01,09:00 AM,05:00 PM,09:14 AM,05:10 PM
2,2026-03-01,09:00 AM,05:00 PM,,
```

**Upload response:**

```json
{
  "filename": "march_2026.csv",
  "records_processed": 42,
  "violations_found": 7
}
```

Rows with an empty `actual_in` are scored as `absence` or `no-call`. Scores
are matched against the first active rule whose `condition` + `threshold` applies.

#### Alerts

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/alerts` | `organization_id`, `limit` | 200 |
| `POST` | `/api/v1/alerts` | — | 201 |

When `organization_id` filter is applied, alerts with `organization_id = NULL`
(platform-wide alerts) are **always included** in the result.

#### Dashboard

| Method | Path | Query Params | Status Codes |
|---|---|---|---|
| `GET` | `/api/v1/dashboard/stats` | `organization_id`, `region_id` | 200 |

```json
// GET /api/v1/dashboard/stats?organization_id=org-1
{
  "total_employees": 24,
  "active_violations": 11,
  "red_flags": 3,
  "total_organizations": 1
}
```

`red_flags` = employees with `points >= 8`.
`active_violations` = count of `AttendanceLog` rows where `violation IS NOT NULL`.

---

### Error Envelope

All errors — including unhandled exceptions — return a consistent envelope:

```json
// 500 Internal Server Error
{
  "error": "unable to open database file",
  "trace_id": "a4b1c2d3-...",
  "detail": { "traceback": "...last 500 chars..." }
}
```

400/404 errors from routers return FastAPI's standard `{"detail": "..."}` format.

---

## 6. Module Map and Responsibilities

```
the_fair_play_initiative/
│
├── app/
│   ├── main.py            FastAPI app factory. Registers all routers under /api/v1.
│   │                      Lifespan hook: create_all() + seed() on every cold start.
│   │                      Serves SPA at GET /. Global exception handler.
│   │
│   ├── config.py          Single Settings class reading all env vars at import time.
│   │                      Singleton `settings` imported everywhere. Zero env = safe defaults.
│   │
│   ├── database.py        SQLAlchemy engine (connect_args for SQLite thread safety).
│   │                      SessionLocal factory. DeclarativeBase. get_db() FastAPI dependency.
│   │
│   ├── models.py          All ORM model classes. M2M join table (organization_region).
│   │                      Mapped columns (SQLAlchemy 2.0 style). All relationships declared
│   │                      with back_populates for bidirectional navigation.
│   │
│   ├── schemas.py         Pydantic v2 models. One Base/Create/Update/Response triplet per entity.
│   │                      from_attributes=True enables ORM → schema serialization.
│   │                      EmployeeDetailResponse nests point_history[].
│   │                      PolicyResponse nests rules[].
│   │
│   ├── seed.py            One-time idempotent demo data loader. Checks if Organization count > 0
│   │                      before inserting. Seeded data: 4 regions, 3 orgs, 5 policies,
│   │                      4 rules per policy, ~30 employees with generated point histories,
│   │                      4 seed alerts. Uses random.Random(42) for reproducible output.
│   │
│   ├── logging.py         generate_trace_id() → UUID4 string.
│   │                      log_request/log_response/log_error → stdout structured logs.
│   │                      Arize Phoenix + OpenTelemetry init (no-op if creds absent).
│   │
│   ├── memory.py          SessionMemory: dict[session_id → list[turns]] + threading.Lock.
│   │                      Singleton instance. Cleared on container restart (in-memory only).
│   │
│   ├── llm.py             get_llm() factory. Returns MockLLM | ChatOpenAI | ChatAnthropic.
│   │                      Graceful fallback: missing API key → warns and returns MockLLM.
│   │
│   ├── chains.py          build_messages(): [SystemMessage] + history + [HumanMessage].
│   │                      run_chain(): calls llm.invoke(), normalizes reply to string.
│   │
│   ├── quotes.py          draft_quotes() stub. Returns {draft_quotes: [], notes: ["..."]}.
│   │                      Has TODO comment for LLM-based PDF extraction.
│   │
│   ├── prompts/           LLM prompt files — one readable Markdown file per prompt.
│   │   ├── 01_keyword_extraction.md   System prompt: extract schema-mapped keywords from policy text.
│   │   ├── 02_sql_query_plan.md       System prompt: devise INSERT plan from keywords.
│   │   │                              Contains {{schema}} placeholder (injected at load time).
│   │   └── schema.json                FPI table schema (9 tables) used in the plan prompt.
│   │
│   ├── services/
│   │   └── policy_analyzer.py         LangGraph pipeline (2 nodes: node_extract → node_plan).
│   │                                   Loads prompts from app/prompts/ at module import.
│   │                                   Extracts text from PDF (pypdf), DOCX (python-docx), TXT.
│   │                                   Uses ChatOpenAI via OpenRouter (OPENROUTER_API_KEY).
│   │                                   Public API: async analyze_policy_document(filename, bytes).
│   │                                   No database writes — returns PolicyAnalysisResponse.
│   │
│   ├── static/
│   │   └── index.html     Full SPA. Tailwind (CDN), Chart.js (CDN), Lucide (CDN).
│   │                      On DOMContentLoaded: calls loadDataFromAPI() which fetches
│   │                      all entities from /api/v1/*. Maps snake_case → camelCase.
│   │                      openEmployeeModal() fetches fresh detail on each open.
│   │                      applyOverride() POSTs to /employees/{id}/override.
│   │                      processAttendanceFile() POSTs CSV as multipart to /attendance/upload.
│   │                      processPolicyFile() POSTs to /api/v1/policies/analyze; renders
│   │                      keyword chips + plan in #analysis-results panel.
│   │                      Falls back gracefully if API unreachable (renders empty UI).
│   │
│   └── routers/
│       ├── regions.py         Full CRUD. Uses db.get(Region, id) for PK lookups.
│       ├── organizations.py   CRUD + manages org.regions M2M list on create/update.
│       ├── policies.py        CRUD with org/region filter. Cascade-deletes rules on DELETE.
│       │                      POST /analyze: accepts UploadFile → calls policy_analyzer service.
│       ├── rules.py           CRUD + PATCH /{id}/toggle endpoint. Filters by policy_id.
│       ├── employees.py       CRUD + GET /{id}/history + POST /{id}/override.
│       │                      Override logic: excuse mutates PointHistory.status → Excused.
│       │                      reduce/reset mutates employee.points. All write audit PointHistory.
│       ├── attendance.py      GET list (ordered by date desc). POST /upload parses CSV,
│       │                      scores each row via _score_row(), writes logs + history.
│       │                      Auto-generates Alert when employee.points >= 8.
│       ├── alerts.py          GET (includes org_id=NULL global alerts when filtered by org).
│       │                      POST creates manually-authored alerts.
│       └── dashboard.py       GET /stats: aggregated counts query. Respects org+region filters.
│
├── agents/
│   ├── tools.py           LangGraph tool stubs (web search, policy lookup)
│   └── workflows.py       LangGraph workflow stubs (ReAct agent graph)
│
├── tests/
│   ├── test_health.py     Integration tests: /health, /chat (mock LLM), /quotes/draft.
│   │                      Uses httpx.AsyncClient with ASGITransport.
│   └── test_fpi_api.py    CRUD integration tests for /api/v1/* endpoints.
│                          Uses in-memory SQLite (DATABASE_URL=sqlite:///:memory:).
│
├── Dockerfile             Production image. Builds on python:3.11-slim.
│                          Installs uv, then deps, then copies app/. Creates data/ dir.
│                          Runs as non-root appuser (UID 1000). Exposes 7860.
├── docker-compose.yml     Local dev compose. Named volume `db_data` → /home/appuser/app/data.
│                          Sets DATABASE_URL=sqlite:///./data/fpi.db so DB survives restarts.
├── requirements.txt       All Python deps. Key additions: sqlalchemy, python-multipart, aiofiles.
└── architecture.md        This document.
```

---

## 7. Execution Flows

### 7.1 Cold Start (Container Startup)

```
uvicorn starts → FastAPI lifespan() hook
  │
  ├─ models.Base.metadata.create_all(bind=engine)
  │    Creates all tables if they don't exist (idempotent).
  │    SQLite file written to /home/appuser/app/data/fpi.db
  │    (mounted Docker volume → survives restarts).
  │
  ├─ seed(db)
  │    Checks: if Organization.count > 0: return  (skip re-seeding)
  │    Inserts: 4 regions → 3 orgs → 5 policies → ~20 rules → ~30 employees
  │             → point histories → 4 alerts
  │    Uses random.Random(42) for reproducible employee names/points.
  │
  ├─ get_llm()  → MockLLM (default) or real LLM if env vars set
  │
  └─ yields → server begins accepting requests
```

### 7.2 SPA Page Load

```
Browser GET /
  └─ FileResponse(app/static/index.html)

index.html loads in browser:
  ├─ CDN scripts (Tailwind, Chart.js, Lucide) load in parallel
  └─ DOMContentLoaded → loadDataFromAPI()
       │
       ├─ Promise.all([
       │    GET /api/v1/organizations,
       │    GET /api/v1/regions,
       │    GET /api/v1/employees,
       │    GET /api/v1/attendance?limit=50,
       │    GET /api/v1/alerts?limit=20,
       │  ])
       │
       ├─ GET /api/v1/policies
       │   → for each policy: GET /api/v1/policies/{id}  (to get nested rules[])
       │
       ├─ GET /api/v1/rules  (global rules with no policy_id)
       │
       ├─ Maps all API snake_case → camelCase local state
       │
       └─ renderDashboard() + renderActiveRules() + lucide.createIcons()
```

### 7.3 CSV Attendance Upload

```
User drags CSV onto dropzone (or selects via file input)
  └─ processAttendanceFile(file)
       │
       ├─ POST /api/v1/attendance/upload  (multipart/form-data, field: "file")
       │
       └─ Backend: attendance.py → upload_attendance()
            │
            ├─ Validates .csv extension (400 if not CSV)
            ├─ Decodes bytes (UTF-8 with BOM → fallback latin-1)
            ├─ DictReader iterates rows
            │
            ├─ For each row:
            │    ├─ Parse employee_id (int) → db.get(Employee)
            │    ├─ Parse date (ISO format → fallback today)
            │    ├─ Fetch active rules for employee.policy_id
            │    │   (or global rules if policy_id is NULL)
            │    │
            │    ├─ _score_row(row, rules):
            │    │    ├─ Parse scheduled_in / actual_in as datetime
            │    │    ├─ For each active rule (in order):
            │    │    │    condition=late:    delta = actual_in - scheduled_in (minutes)
            │    │    │                       if delta > threshold → violation
            │    │    │    condition=early:   delta = scheduled_out - actual_out
            │    │    │                       if delta > threshold → violation
            │    │    │    condition=absence: if actual_in empty → violation
            │    │    │    condition=no-call: if both in+out empty → violation
            │    │    └─ Returns (violation_name, points) for FIRST matching rule
            │    │
            │    ├─ Write AttendanceLog row
            │    ├─ If violation:
            │    │    ├─ Add PointHistory row (status=Active)
            │    │    ├─ employee.points += pts
            │    │    └─ If employee.points >= 8:
            │    │         Insert Alert (type=danger, org-scoped)
            │    └─ records_processed++
            │
            ├─ db.commit()
            └─ Return { filename, records_processed, violations_found }

Frontend on success:
  ├─ Reload /api/v1/attendance → update state.processedLogs
  ├─ Reload /api/v1/employees → update state.employees (fresh points)
  ├─ updateStats() + renderProcessedLogs() + renderEmployees()
  └─ showToast("Processed N records, M violations found")
```

### 7.4 Manual Override

```
Admin opens employee modal → selects override type → clicks Apply
  └─ applyOverride()
       │
       ├─ POST /api/v1/employees/{id}/override
       │    body: { type: "excuse"|"reduce"|"reset", amount?, reason }
       │
       └─ Backend: employees.py → apply_override()
            │
            ├─ excuse:
            │   Find newest PointHistory where status=Active
            │   Set status → Excused
            │   employee.points -= latest.points  (floor 0)
            │   Write audit PointHistory: type="Manual Override: excuse", points=negative
            │
            ├─ reduce:
            │   employee.points = max(0, points - amount)
            │   Write audit PointHistory: type="Manual Override: reduce", points=-amount
            │
            ├─ reset:
            │   Mark ALL Active PointHistory → Excused
            │   employee.points = 0
            │   Write audit PointHistory: type="Manual Override: reset"
            │
            └─ db.commit() → return EmployeeDetailResponse (with refreshed history[])
```

### 7.5 Policy Document Analysis

```text
User selects PDF/DOCX/TXT on Policy Management tab
  └─ processPolicyFile(file)   [app/static/index.html]
       │
       ├─ Shows spinner in dropzone
       ├─ POST /api/v1/policies/analyze  (multipart/form-data)
       │
       └─ Backend: policies.py → analyze_policy()
            │
            ├─ Validate extension (.pdf / .docx / .doc / .txt)
            ├─ Read file bytes
            └─ await analyze_policy_document(filename, bytes)
                 │   [app/services/policy_analyzer.py]
                 │
                 ├─ Extract text:
                 │    PDF  → pypdf.PdfReader
                 │    DOCX → python-docx Document
                 │    TXT  → utf-8 decode
                 │
                 ├─ LangGraph invoke:  START → node_extract → node_plan → END
                 │
                 ├─ node_extract:
                 │    LLM: ChatOpenAI (OpenRouter, gpt-4o-mini)
                 │    System: app/prompts/01_keyword_extraction.md
                 │    Human:  pdf_text[:4000]
                 │    Output: KeywordExtraction (structured, 8 entity groups + confidence)
                 │
                 └─ node_plan:
                      LLM: ChatOpenAI (OpenRouter, gpt-4o-mini)
                      System: app/prompts/02_sql_query_plan.md + schema.json
                      Human:  formatted keywords + pdf_text[:2000]
                      Output: SQLQueryPlan (tables, joins, filters, cte_description + confidence)

Frontend on success:
  ├─ renderAnalysisResults(data)
  │    ├─ #keywords-section: color-coded chips per entity group
  │    └─ #plan-section: objective, tables, joins, existence checks, column mappings
  ├─ Show #analysis-results panel
  └─ showToast("Analysis complete!")

No database writes at any stage.
```

### 7.6 Chatbot Request

```
POST /chat  { session_id, message }
  │
  ├─ generate_trace_id()      → UUID4
  ├─ log_request()
  ├─ session_memory.get_history(session_id)
  │    thread-safe dict lookup, returns list of (role, content) pairs
  │
  ├─ chains.build_messages(history, message)
  │    → [SystemMessage("You are FPI assistant...")]
  │       + [HumanMessage/AIMessage ...history turns]
  │       + [HumanMessage(message)]
  │
  ├─ llm.invoke(messages)
  │    MockLLM: returns "MOCK_REPLY: <message>"  (deterministic, no API call)
  │    OpenAI:  calls GPT-4 (or LLM_MODEL env var)
  │    Anthropic: calls Claude
  │
  ├─ session_memory.append(session_id, "human", message)
  ├─ session_memory.append(session_id, "ai", reply)
  ├─ log_response()
  └─ return ChatResponse { session_id, reply, trace_id, citations:[], debug:{provider} }
```

---

## 8. Configuration Reference

All config is loaded at import time in `app/config.py`. The app starts safely with **zero env vars**.

| Variable | Default | When to change |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./fpi.db` | Set to `sqlite:///./data/fpi.db` in Compose (volume path). Set to `postgresql://user:pass@host/db` for production. |
| `LLM_PROVIDER` | `mock` | `openai` or `anthropic` to use a real LLM |
| `LLM_MODEL` | _(empty)_ | e.g. `gpt-4o` — falls back to provider default if unset |
| `LLM_API_KEY` | _(empty)_ | Generic — provider-specific keys below take precedence |
| `OPENAI_API_KEY` | _(empty)_ | Used when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | _(empty)_ | Used when `LLM_PROVIDER=anthropic` |
| `OPENROUTER_API_KEY` | _(empty)_ | **Required for Policy Analyzer.** Used by `app/services/policy_analyzer.py` as the LLM API key (`base_url=https://openrouter.ai/api/v1`). If unset, `/policies/analyze` returns 503. |
| `APP_HOST` | `0.0.0.0` | Rarely needs changing inside a container |
| `APP_PORT` | `7860` | Must match Dockerfile `EXPOSE` and compose `ports` |
| `ARIZE_API_KEY` | _(empty)_ | Set to enable Arize Phoenix distributed tracing |
| `ARIZE_SPACE_ID` | _(empty)_ | Required alongside `ARIZE_API_KEY` |

> **Security:** Never commit real secrets to the repository.
> Use `.env` (git-ignored) for local dev, and inject secrets via the deployment
> platform's secrets manager (HF Spaces → Repository Secrets; Docker → `--env-file`).

---

## 9. Docker and Deployment

### Image Build Sequence

```dockerfile
FROM python:3.11-slim

RUN useradd -m -u 1000 appuser       # Non-root user (required by HF Spaces)
WORKDIR /home/appuser/app

RUN pip install --no-cache-dir uv    # Bootstrap uv package manager
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt  # Fast dep install

COPY app/ ./app/                     # Source code (includes static/index.html)

RUN mkdir -p /home/appuser/app/data && \     # IMPORTANT: data/ must exist before
    chown -R appuser:appuser /home/appuser/app   # volume mount or SQLite will fail

USER appuser
ENV LLM_PROVIDER=mock
ENV APP_PORT=7860
EXPOSE 7860
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

> **Why `mkdir data/` in the Dockerfile?**
> Docker named volumes are mounted **over** the directory they target. If `data/`
> doesn't exist in the image layer when the volume is attached, the mount point
> is created by Docker as `root:root` — and the non-root `appuser` cannot write
> `fpi.db` into it. Creating `data/` in the `RUN` layer and `chown`ing it ensures
> `appuser` always has write access, regardless of volume attachment order.

### Compose Setup (Local Dev)

```yaml
services:
  api:
    build: .
    image: fair-play-backend
    ports: ["7860:7860"]
    volumes:
      - db_data:/home/appuser/app/data    # SQLite persistence
    environment:
      DATABASE_URL: sqlite:///./data/fpi.db
      LLM_PROVIDER: mock
    restart: unless-stopped

volumes:
  db_data:
```

**Common commands:**

```sh
docker compose up --build -d   # Build image + start detached
docker compose logs -f         # Tail logs
docker compose down            # Stop (volume preserved)
docker compose down -v         # Stop + wipe database (re-seeds on next up)
docker compose restart         # Restart without rebuild
```

### Hugging Face Spaces Deployment

1. Push this repo to a Hugging Face Space with **SDK: Docker**
2. HF builds the root `Dockerfile` automatically
3. Port 7860 is exposed by default
4. Set secrets in **Space Settings → Repository Secrets**:
   - `OPENAI_API_KEY` (if using OpenAI)
   - `DATABASE_URL` (point to a hosted Postgres for persistence)

> **HF Spaces limitation:** The container filesystem is ephemeral. Without a PostgreSQL
> `DATABASE_URL`, the SQLite database resets on every Space restart. For a persistent
> HF deployment, set `DATABASE_URL` to a Supabase or Neon PostgreSQL connection string.

---

## 10. Observability

| Signal | Mechanism |
|---|---|
| **Trace IDs** | Every request generates a UUID4 `trace_id`. Included in structured logs and in API responses (`ChatResponse.trace_id`, `ErrorResponse.trace_id`). |
| **Structured logs** | `level=INFO endpoint=/chat trace_id=... status=ok` format to stdout. |
| **Distributed tracing** | Arize Phoenix + OpenTelemetry initialized on startup if `ARIZE_API_KEY` is set. Silently no-ops (catches `ImportError` and missing key) otherwise. |
| **LLM observability** | Future: LangSmith trace wrapping or Arize LLM span logging. |

---

## 11. Testing

```sh
pytest tests/ -v                               # Run all tests
pytest tests/test_health.py -v                 # Core smoke tests only
pytest tests/test_fpi_api.py -v                # FPI CRUD tests only
pytest tests/ -v --tb=short --log-cli-level=INFO  # With logs
```

`test_fpi_api.py` uses an in-memory SQLite database
(`DATABASE_URL=sqlite:///:memory:` injected via `pytest` fixture) so tests are
isolated, stateless, and fast — no Docker required for the test suite.

---

## 12. Planned Evolution

| Item | Description |
|---|---|
| **Alembic migrations** | Replace `create_all()` with versioned migration history. Required before any schema change in production. |
| **PostgreSQL** | Swap `DATABASE_URL` — no code changes needed. SQLAlchemy handles both dialects transparently. |
| **Redis session store** | Replace in-memory `SessionMemory` so `/chat` sessions survive container restarts and scale across replicas. |
| **Authentication** | JWT middleware (FastAPI-Users or custom). Bind `session_id` to authenticated user. Role-based: Admin vs. Employee view. |
| **LangGraph orchestration** | Replace linear `run_chain()` with a stateful graph agent: `retrieve → reason → respond` nodes with tool calling (web search via Tavily, policy DB lookup). |
| **RAG — Policy ingestion** | Upload PDF policy handbooks. LangChain PDF loader + text splitter → embeddings → vector store (Chroma/Pinecone). Retriever node feeds context into chatbot. |
| ~~Rule extraction from PDFs~~ | ✅ **Done (v0.3.0)** — `/api/v1/policies/analyze` uses a 2-node LangGraph pipeline to extract keywords and produce a structured ingestion plan from uploaded policy documents. |
| **Streaming chat replies** | Switch `/chat` to `StreamingResponse` using LangGraph's `.astream()`. |
| **Scheduled point resets** | Cron job (APScheduler or Celery) to zero employee points at end of rolling window (`next_reset` date). |
| **Employee self-service portal** | Separate read-only view for employees to see their own history. |
| **Excel upload support** | Extend `attendance/upload` to accept `.xlsx` via `openpyxl`. |
| ~~OpenRouter gateway~~ | ✅ **Done (v0.3.0)** — Policy Analyzer uses `ChatOpenAI` with `base_url=https://openrouter.ai/api/v1` and `OPENROUTER_API_KEY`. Chatbot still uses provider-direct; consolidation is a future item. |
