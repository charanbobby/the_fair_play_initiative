# Notebook Change History — Conversations with Claude

> File: `experiments/01_pdf_to_db_query.ipynb`
> Ordered by conversation session, most recent last.

---

## Session 1 — Mar 3, 2026

### Initial notebook setup

Built the first working version of the PDF → SQL pipeline from scratch.

- **Pipeline:** `PDF (PyMuPDF) → litellm + instructor → structured output → SQLite validation`
- **Pydantic model:** Single `QueryExtraction` with `keywords: list[str]`, `sql_query: str`, `confidence_score: float`
- **Database:** 8-table in-memory SQLite schema defined inline in the notebook
- **Infrastructure:** Created `Dockerfile`, `docker-compose.yml`, and `requirements-experiments.txt` for the containerized Jupyter environment
- **SQL Explorer:** Added `run_query(sql)` helper cell for manual ad-hoc queries

---

## Session 2 — Mar 4, 2026 (morning)

### Cell restructuring + Pydantic model split

Reorganized notebook cells and began separating concerns.

- Split keyword extraction and SQL generation into **separate, independently runnable cells**
- Renamed/redesigned the output model: `KeywordExtraction` now has **per-table fields** matching the FPI schema (`policy`, `organization`, `region`, `rule`, `attendance_log`, `point_history`, `alert`, `other_relevant_terms`) instead of a flat keyword list
- Added a second model `SQLGeneration` with `sql_query` + `confidence_score`
- Externalised the schema and prompt into dedicated files: `Schema.json` (9-table FPI schema) and `SystemPrompt.md`
- The full system message is now assembled at runtime: `SystemPrompt.md` + `Schema.json` block appended

---

## Session 3 — Mar 4, 2026 (afternoon)

### LangChain migration + observability + LangGraph pipeline

Major architecture overhaul — replaced the ad-hoc `litellm + instructor` approach with a proper LangChain + LangGraph pipeline.

#### Framework switch

- Replaced `litellm + instructor` with **LangChain** (`init_chat_model`, `ChatPromptTemplate`, `with_structured_output`)
- Model: `gpt-5-mini` via OpenRouter

#### Observability

- Added **Arize AX** tracing (OpenTelemetry / OTLP over gRPC) — every LLM call becomes a span in the `fair-play-initiative` project
- Added `MetricsCallback` (LangChain `BaseCallbackHandler`) to capture latency (ms) and token counts (prompt / completion / total) locally inside the notebook session
- Added a "Session Summary" cell: prints a table of all LLM calls this session + human eval label breakdown

#### LangGraph agent

- Defined typed state `FPIState` (`pdf_text`, `extraction`, `query_results`, `error`)
- Two nodes: `node_extract` (keyword extraction) → `node_execute` (SQL against SQLite)
- Graph: `extract → execute → END`, compiled as `fpi_agent`
- Invoked with `MetricsCallback` for full observability

#### Human evaluation widget

- Added `review_extraction()` using `ipywidgets` — renders categorized keyword output, SQL draft, a `good / partial / bad` label toggle, and free-text notes
- Reviews accumulated in `human_reviews` list for the session

#### Verified live outputs

- Keyword extraction: confidence `0.98`, 74 terms across 8 categories from the HR-811-A policy
- LangGraph agent: confidence `0.92`, complex CTE-based SQL generated and syntax-validated against the empty schema

---

## Session 4 — Mar 5, 2026

### Decomposition prompting — plan before executing

Key design decision: instead of asking the LLM to write a large SQL query in one shot, split it into a **plan → review → generate** sequence.

**Why:** The single-shot approach works but produces opaque SQL that's hard to verify. A structured plan lets a human (or automated reviewer) catch logic errors before any SQL runs.

#### New Pydantic models designed

- `TableUsage` — which table, which columns used, why
- `JoinStep` — tables joined, conditions, join type (INNER / LEFT / etc.)
- `FilterCondition` — WHERE and HAVING clause conditions
- `AggregationStep` — GROUP BY columns, aggregate functions
- `SQLQueryPlan` — top-level plan model composing the above
- All sub-models defined as **top-level classes** (not nested) to produce cleaner JSON Schema for the LLM

#### LangGraph redesign

- Old graph: `extract → execute → END`
- New graph: `extract → plan → generate_sql → execute → END`
- New `node_plan`: takes `KeywordExtraction` + PDF text → produces `SQLQueryPlan`
- New `node_generate_sql`: takes the approved plan → produces final `SQLGeneration`
- Plan is retained in `FPIState` for traceability in Arize AX

#### SQL validation strategy

Decided to implement two complementary approaches:

1. **Targeted seed data** — 5 employee rows that each hit a different escalation threshold (Coaching Conference, Formal Warning, Final Warning, Termination Review, No Action) so the SQL output can be verified end-to-end
2. **CTE decomposition testing** — run the inner CTE alone first to validate joins and filters before running the full query

Discussed but deferred: EXPLAIN QUERY PLAN (structure only), Supabase SQL Editor (real data), LLM self-review node.

#### Cells modified

| Cell ID | Change |
| ------- | ------ |
| After `vcei3qawk69` | INSERT — SQLQueryPlan model definitions (5 Pydantic classes) |
| After `ece5d4da` | INSERT — PLAN_PROMPT setup + plan runner with `_format_plan()` |
| `ppsjy4cxjvj` | REPLACE — now `PLAN_GUIDED_SQL_SYSTEM_MSG` + `_format_plan_for_sql_prompt()` + runner → `sql_data` |
| `9fef6d78` | EDIT — schema creation unconditional; validation guard changed to `sql_data` |
| `tunbt9a3e7g` | EDIT — diagram updated to `extract → plan → generate_sql → execute` |
| `uohs84lvr9` | REPLACE — new `FPIState` + 4 nodes + graph wiring |
| `hbh4chsjm3t` | REPLACE — updated invocation (6-key state) + updated print block |

#### Other decisions

- Arize AX monitoring deemed sufficient for plan review — the `ipywidgets` human review widget can be removed or repurposed
- `node_extract` preserved unchanged; new nodes insert after it

---

## Session 9 — Mar 5, 2026

### Distillation notes revised — closing gap between Sonnet 4.6 gold standard and gpt-5-mini

#### Problem

After Session 8 distillation, gpt-5-mini output degraded after prompt tweaks. Root cause: four structural gaps between what the prompt instructed and what Sonnet 4.6 actually produced.

#### Gap analysis

| Gap | Effect on gpt-5-mini |
| --- | -------------------- |
| `cte_description` underdefined — prompt said "describe what the CTE computes and why" | Model produced 1–2 sentences; Sonnet produced a full procedural plan with all column mappings + all 35 rule rows |
| `joins` field purpose unspecified for ingestion | Model filled joins with SQL-style join descriptions or left it wrong; Sonnet used it as FK dependency chains |
| Column mapping location unclear — planning rule 2 said "identify every column" without saying where | gpt-5-mini packed mappings into `purpose` (one sentence); they belong in `cte_description` |
| `rule.points` sign convention not stated | Model produced 0.0 for PA reductions instead of negative values (-0.5, -1.0, -1.5, -2.0) |

#### Changes (cell mpundg7z6lj)

1. **`cte_description` section** — replaced vague Pydantic description with explicit 4-part checklist: (1) numbered table steps with column-to-keyword mappings, (2) full rule enumeration in four named groups + operational rows, (3) ID chaining summary, (4) operational reminders/placeholders.

2. **`joins` section** — added explicit definition for ingestion use: `left` = child table (holds FK), `right` = parent table (holds PK), `condition` = FK = PK expression, `join_type` = 'INNER' always. Made clear these are NOT SQL joins.

3. **Rule row section** — expanded to name specific violation types (NCNS 1st day, NCNS consecutive, tardy major, tardy minor, third minor tardy, etc.) and approved-leave types (FMLA, ADA, PTO, jury, military, bereavement, workers comp, STD) so model doesn't stop early.

4. **`rule.points` sign** — added explicit sign convention: positive for violations, 0.0 for approved-leave/CA triggers, NEGATIVE for PA reductions.

5. **Planning rules** — rule 2 redirected joins to FK dependency chain format; rule 4 made explicit: column mappings and rule enumerations go in `cte_description`, NOT in `tables_required.purpose`.

---

## Session 8 — Mar 5, 2026 (earlier)

### Prompt distillation: encode Sonnet 4.6 reasoning into gpt-5-mini system prompt

#### Approach

After one run with `claude-sonnet-4-6` as the plan model, the output plan was high quality but latency was 90s (14,920 tokens — 9,428 prompt / 5,492 completion). Switched back to `gpt-5-mini` for cost/speed, but injected a **PLANNING GUIDANCE** block into `PLAN_SYSTEM_MSG` that encodes the key structural decisions Sonnet 4.6 produced.

This is prompt distillation: use the stronger model once to discover the correct reasoning pattern, then make that pattern explicit in the smaller model's instructions so it doesn't have to rediscover it.

#### Distilled reasoning captured from Sonnet 4.6 run

From the Sonnet 4.6 plan (confidence 0.87, 23 rule rows, full CTE chain):

| Pattern | Guidance encoded |
| ------- | ---------------- |
| INSERT order | `organization → region → organization_region → policy → rule` (FK constraint chain) |
| INSERT OR IGNORE vs INSERT OR REPLACE | org/region/junction = IGNORE (master data); policy = REPLACE (revisions supersede); rule = REPLACE (thresholds change) |
| ID chaining | `uses_cte = True` always; describe full org_id → region_id → policy_id → rule.policy_id chain |
| Rule row granularity | One row per violation type; one per approved-leave type (0.0 pts); one per perfect-attendance milestone (negative pts, threshold = clean days); one per CA level (0.0 pts, threshold = lower bound of point range) |
| Value derivation | Slug IDs (kebab-case); `region.labor_laws` as comma-separated TEXT; `region.code`/`timezone` as named placeholders if not in policy |
| Natural keys for existence checks | org: name OR code; region: code; junction: composite; policy: name + org_id; rule: policy_id + name |

#### Notebook changes

| Cell ID | Change |
| ------- | ------ |
| `mpundg7z6lj` | Added `PLANNING GUIDANCE` block to `PLAN_SYSTEM_MSG`; switched `plan_model` back to `model` (gpt-5-mini) |
| `uohs84lvr9` | Switched `lg_plan_model` back to `model`; updated comment to `# gpt-5-mini + distillation notes` |

`plan_model_base` (claude-sonnet-4-6) remains defined in cell `ece5d4da` for easy re-activation if distillation proves insufficient.

---

## Session 7 — Mar 5, 2026

### Prompt reframe: pipeline purpose is policy ingestion, not analytics

#### Problem

The `SQLQueryPlan.objective` was generating descriptions like *"Produce a comprehensive attendance compliance dashboard..."*. This is the downstream *use* of the policy data, not what the pipeline is doing. The pipeline's job is to **upload/ingest the policy document** — INSERT the organisation, region, policy metadata, and rules into the FPI configuration tables so the system can use them at runtime.

The model was inferring the analytics goal from the policy keywords and generating a SELECT-oriented plan. The actual SQL should be INSERT/UPSERT, not SELECT.

#### Root cause

`PLAN_SYSTEM_MSG` said *"answer the business question implied by those keywords"* — unambiguously biasing toward SELECT. The model correctly read the policy, understood its downstream purpose, and planned accordingly. The prompt was wrong, not the model.

#### Changes

**`SQLQueryPlan.objective` field description** (cell `r2zr6mh5s`)

- Old: `"One sentence: what business question does this query answer?"`
- New: explicitly says *"For ingestion plans, describe what data is being inserted and into which tables. Do NOT describe downstream analytics or reporting use cases."*
- `grouping_columns`, `aggregations`, `having_filters`, `output_columns` descriptions updated with *"Leave empty for ingestion plans."*

**`PLAN_SYSTEM_MSG`** (cell `mpundg7z6lj`)

- Role changed from *"SQL query planning assistant"* → *"SQL ingestion planning assistant"*
- Explicit **TARGET TABLES**: `organization`, `region`, `organization_region`, `policy`, `rule`
- Explicit **OFF-LIMITS TABLES**: `employee`, `attendance_log`, `point_history`, `alert`
- Planning rules rewritten: INSERT order (respects FK constraints), column-to-keyword mapping, INSERT OR IGNORE vs INSERT OR REPLACE decision, value derivation (slug IDs, JSON arrays)
- Human message updated: *"Devise an ingestion plan"* not *"Devise a query plan"*

**`PLAN_GUIDED_SQL_SYSTEM_MSG`** (cell `ppsjy4cxjvj`)

- Role changed: generates INSERT/UPSERT, not SELECT
- Explicit prohibitions: no SELECT, UPDATE, DELETE; no transactional tables
- SQLite rules added: slug ID generation, ISO 8601 dates, labor_laws as TEXT
- `_format_plan_for_sql_prompt()` updated: "Tables (in INSERT order)", "Existence checks / WHERE" instead of "WHERE"
- Human message updated: *"Generate INSERT SQL"*, keywords described as *"source values for INSERT literals"*

#### Conceptual clarification captured

The FPI schema has two categories of tables:

| Category | Tables | Populated by |
| -------- | ------ | ------------ |
| Configuration | `organization`, `region`, `organization_region`, `policy`, `rule` | Policy ingestion pipeline (this notebook) |
| Transactional | `employee`, `attendance_log`, `point_history`, `alert` | HR system at runtime |

Policy ingestion only touches configuration tables. The pipeline is a document-to-database loader, not a reporting tool.

---

## Session 6 — Mar 5, 2026

### Split model strategy — Claude Sonnet 4.6 for explainability only

#### Issue

The plan step (Step 3b / `node_plan`) was producing low-quality `SQLQueryPlan` output with `gpt-5-mini`. Specifically: join conditions were ambiguous, filter expressions were vague, and `source_keyword` fields weren't matching actual extracted terms. The plan is the only step a human can review before SQL is written — poor explainability here means errors propagate silently to SQL generation.

#### Decision: heterogeneous model routing

Use a stronger model only where it matters most, keeping cost/latency low everywhere else:

| Step | Node | Model | Reason |
| ---- | ---- | ----- | ------ |
| 3a keyword extraction | `node_extract` | `gpt-5-mini` | Structured classification task — fast model sufficient |
| 3b query plan | `node_plan` | `claude-sonnet-4-6` | Requires multi-step relational reasoning across 9 tables; this is the explainability checkpoint |
| 3c SQL generation | `node_generate_sql` | `gpt-5-mini` | Input is a fully-specified plan — model just implements it; fast model sufficient |

#### Why `employee.id` is necessary in the JOIN chain

A design question came up about the JOIN structure being planned:

```sql
INNER JOIN o ON e.organization_id = o.id
INNER JOIN r ON e.region_id = r.id
INNER JOIN p ON e.policy_id = p.id
LEFT JOIN e ON a.employee_id = e.id          ← bridge join
LEFT JOIN ru ON ru.policy_id = p.id AND ru.name = a.violation
```

`employee.id` is required because:

1. `attendance_log.employee_id` is a FK — it stores a numeric ID only, not names or department
2. The three INNER JOINs use `e.organization_id`, `e.region_id`, `e.policy_id` — `e` must be in scope for those expressions to resolve
3. `attendance_log` has its own denormalized `organization_id`/`region_id`/`policy_id` columns, but routing through `e` lets us filter/group by employee attributes (department, position, etc.) at the same time
4. The `LEFT JOIN` (not INNER) means employees with no attendance events are still returned — correct for a summary report

#### First run metrics (plan node — claude-sonnet-4-6)

| Metric | Value |
| ------ | ----- |
| Timestamp | 2026-03-05T11:18:15 |
| Latency | 59,359 ms |
| Prompt tokens | 4,863 |
| Completion tokens | 2,488 |
| Total tokens | 7,351 |

Latency is high (~59s) — expected for a first run; the plan step has a large system prompt (full schema + planning rules) and produces a deeply structured `SQLQueryPlan` with many sub-model fields. Baseline to compare against after prompt tuning.

#### Model wiring changes

| Cell ID | Change |
| ------- | ------ |
| `ece5d4da` | Added `plan_model_base` (claude-sonnet-4-6 via OpenRouter); added comments identifying each model's role |
| `mpundg7z6lj` | Changed `plan_model = model.with_structured_output(...)` → `plan_model = plan_model_base.with_structured_output(...)` |
| `uohs84lvr9` | Changed `lg_plan_model = model.with_structured_output(...)` → `lg_plan_model = plan_model_base.with_structured_output(...)`; added inline comments for all three model bindings |

---

## Session 5 — Mar 4, 2026

### Bug fix: missing `_format_keywords` + readable plan format

Two issues discovered and fixed after running the decomposition pipeline for the first time.

#### Bug: `_format_keywords` not defined

- Steps 3b and 3c were silently failing with `name '_format_keywords' is not defined`
- The helper was called in 3 places (plan runner, SQL runner, LangGraph nodes) but never defined
- Fix: added `_format_keywords(kw: KeywordExtraction) -> str` to the model setup cell (`ece5d4da`), before all downstream cells that need it
- Iterates `_KEYWORD_FIELDS`, formats non-empty lists as `[field]\n  • value` sections

#### Fix: `_format_plan_for_sql_prompt()` — structured format

- Original implementation packed every section into semicolon-delimited single lines (Tables, Joins, WHERE, Aggregations all on one line each)
- This was unreadable in Arize AX traces and degraded SQL model accuracy — confidence dropped from ~0.86 (plan) to 0.65 (SQL)
- Rewrote to put each item on its own indented line under a named section header:

```text
Tables:
  organization AS o — purpose...
  region AS r — purpose...

Joins:
  INNER JOIN region AS r ON p.region_id = r.id
  ...

WHERE:
  p.name = 'HR-811-A'
  p.active = TRUE
  ...
```

- Sections are conditionally included (skipped when empty)
- Cell modified: `ppsjy4cxjvj`
