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

## Session 10 — Mar 5, 2026

### Step 3c — SQL generation refinements

Upgraded the SQL generation step (Step 3c) from a minimal stub to a fully structured, externally-prompted pipeline stage with proper multi-statement execution and post-INSERT verification.

#### New file: `experiments/SQLGenPrompt.md`

Externalized the SQL generation system prompt (previously hardcoded in cell `ppsjy4cxjvj`). Follows the same `{{schema}}` placeholder pattern as `SystemPrompt.md` and the plan prompt (`02_sql_query_plan.md`). Also saved a copy at `app/prompts/03_sql_generation.md` for the backend.

Key prompt sections: hard constraints (no SELECT/UPDATE/DELETE, no transactional tables), INSERT order (FK chain), ID chaining rules, per-rule-row generation spec, value quality guidelines, confidence scoring rubric.

#### `SQLGeneration` model expanded (cell `vcei3qawk69`)

Old model had 2 fields (`sql_query`, `confidence_score`). New model has 6:

| Field | Type | Purpose |
| ----- | ---- | ------- |
| `sql_query` | `str` | Raw executable SQL block |
| `tables_affected` | `list[str]` | Ordered list of tables receiving INSERTs |
| `statement_count` | `int` | Total INSERT count |
| `rule_count` | `int` | Rule INSERTs specifically (subset) |
| `id_chain` | `dict[str, str]` | Slug IDs used across statements (for FK tracing) |
| `confidence_score` | `float` | 0.0–1.0 with deduction rubric |

#### Step 3c cell updated (cell `ppsjy4cxjvj`)

- Prompt loaded from `SQLGenPrompt.md` file instead of inline string
- `_format_plan_for_sql_prompt()` improved: FK chain now shows `left.FK → right.PK`, existence checks include `source_keyword`
- Output prints all new metadata fields (`statement_count`, `rule_count`, `tables_affected`, `id_chain`)

#### SQL validation cell rewritten (cell `9fef6d78`)

- `cursor.execute()` → `cursor.executescript()` to handle multi-statement INSERT blocks
- Added `organization_regions` junction table to the in-memory schema (was missing)
- Changed `rules.id` from `INTEGER AUTOINCREMENT` → `TEXT PRIMARY KEY` (matches slug ID convention)
- Added post-INSERT verification: row-count table for all 5 config tables + rule detail breakdown (id, points, threshold)

#### LangGraph `node_execute` updated (cell `uohs84lvr9`)

- `cur.execute()` → `cur.executescript()` for multi-statement SQL
- Returns `dict` of row counts per config table instead of empty row list
- `FPIState.query_results` type changed from `list[dict]` → `dict`

#### Cells modified

| Cell ID | Change |
| ------- | ------ |
| `vcei3qawk69` | REPLACE — expanded `SQLGeneration` model (2 → 6 fields) |
| `ppsjy4cxjvj` | REPLACE — load prompt from file, improved plan formatter, richer output |
| `9fef6d78` | REPLACE — `executescript()`, added junction table, TEXT rule IDs, row-count verification |
| `uohs84lvr9` | REPLACE — `node_execute` uses `executescript()`, returns row counts |

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

---

## Session 11 — Mar 5, 2026

### RAG optimisation — ChromaDB vector retrieval to replace brute-force truncation

#### Problem

The current pipeline (`01_pdf_to_db_query.ipynb`) takes **316.7s** with **36k tokens** (gpt-5-mini, ~$0.0008). Both `node_extract` and `node_plan` receive blindly truncated text (`pdf_text[:4000]` and `pdf_text[:2000]`), wasting tokens on irrelevant sections while potentially missing critical policy details beyond the truncation boundary.

#### Solution: Retrieval-Augmented Generation (RAG)

Created `experiments/02_rag_pipeline.ipynb` — a new experiment notebook that introduces a ChromaDB-based RAG retrieval step before the LLM nodes.

**Reference implementation:** `D:\Python Applications\problem_first_ai\Perplexia\perplexia_ai\week2\part2.py` (DocumentRAGChat using ChromaDB + OpenAIEmbeddings via OpenRouter).

#### Architecture

**Old graph:** `START → node_extract → node_plan → END`
**New graph:** `START → node_retrieve → node_extract → node_plan → END`

**New state field:**
- `rag_context: str | None` — concatenated relevant chunks retrieved from ChromaDB

**New node: `node_retrieve`**
1. Chunks full PDF text with `RecursiveCharacterTextSplitter` (800 chars, 200 overlap)
2. Embeds chunks into ephemeral ChromaDB collection (in-memory, no persistence)
3. Runs 5 schema-aware similarity queries (k=8 each), deduplicates results
4. Joins unique retrieved chunks with `---` separators into `rag_context`

**Schema-aware retrieval queries:**

| Query | Target entities |
| ----- | --------------- |
| `attendance policy rules violations points thresholds escalation corrective action` | rule, policy |
| `organization company employer region location jurisdiction labor laws` | organization, region |
| `policy name effective date scope accrual model rolling window` | policy metadata |
| `excused unexcused absence tardy no-call no-show early departure` | attendance_log, rule |
| `perfect attendance reduction milestone FMLA ADA PTO leave approved` | point_history, rule |

**Modified nodes:**
- `node_extract`: uses `state["rag_context"]` instead of `state["pdf_text"][:4000]`; falls back to truncation if RAG context is missing
- `node_plan`: uses `state["rag_context"]` instead of `state["pdf_text"][:2000]`; same fallback

#### Chunking strategy

| Parameter | Value | Rationale |
| --------- | ----- | --------- |
| `chunk_size` | 800 | Large enough to preserve paragraph context; small enough for precise retrieval |
| `chunk_overlap` | 200 | Prevents losing information at chunk boundaries |
| `separators` | `\n\n`, `\n`, `. `, ` `, `` | Prioritises paragraph → sentence → word boundaries |

#### Embedding model

- `text-embedding-3-small` via OpenRouter (same provider as LLM)
- Uses `OpenAIEmbeddings` from `langchain-openai`

#### Dependencies added

- `langchain-chroma>=0.2.0` — ChromaDB integration for LangChain
- `langchain-text-splitters>=0.3.0` — text chunking utilities
- Added to `experiments/requirements-experiments.txt`; `langchain-chroma==1.1.0` already exists in root `requirements.txt`

#### Expected improvements

- **Token reduction:** RAG context should be significantly smaller than 4000-char truncation while covering more relevant content
- **Speed:** fewer input tokens → faster LLM inference
- **Quality:** retrieval targets specific schema entities instead of hoping the first N chars contain everything

#### Files created/modified

| File | Change |
| ---- | ------ |
| `experiments/02_rag_pipeline.ipynb` | NEW — full RAG experiment notebook (observability, chunking, embedding, retrieval, extraction, plan, LangGraph agent, performance comparison) |
| `experiments/requirements-experiments.txt` | EDIT — added `langchain-chroma>=0.2.0` and `langchain-text-splitters>=0.3.0` |

#### Actual results (ran the notebook)

| Metric | Baseline (01) | RAG (02) | Delta |
| ------ | ------------- | -------- | ----- |
| Latency | 316.7s | 584.8s | 1.8x slower |
| Tokens | 36,000 | 64,656 | +80% more |
| Chunks retrieved | n/a | 20 of 26 | 97.3% of document |

**Conclusion: RAG does not help this use case.** The pipeline performs *exhaustive structured extraction* — it needs every rule, threshold, leave type, and escalation level from the policy. RAG retrieved 97.3% of the document anyway, so the embedding + retrieval step added pure overhead with no token savings.

#### When RAG would add value in FPI

- **Cross-policy querying** (50+ ingested policies) — retrieve relevant chunks from the right policy instead of feeding all documents
- **Runtime Q&A** ("what happens after 9 points?") — pull the right section from the right policy for a user question
- **Documents exceeding LLM context window** (128K+) — can't fit everything in one prompt, RAG is mandatory

**Key insight:** For single-document exhaustive extraction, pass the full text. RAG adds value when you have more content than fits in context and only need a subset to answer a question.

---

## Session 12 — Mar 5, 2026

### Code audit: duplicate PDF upload safety

**Question:** What happens if the same policy PDF is uploaded/analyzed a second time?

**Finding:** The analysis pipeline is completely stateless and read-only.

1. `POST /api/v1/policies/analyze` (`app/routers/policies.py:79-105`) — accepts multipart upload, extracts text, runs the 2-node LangGraph (`node_extract → node_plan`), returns `PolicyAnalysisResponse`. Zero database interaction.
2. `analyze_policy_document()` (`app/services/policy_analyzer.py`) — both nodes are LLM calls only. No INSERT, no UPDATE, no SQL execution.
3. Separate `POST /api/v1/policies` (`app/routers/policies.py:39-47`) — this manual endpoint *does* write to the DB and checks for duplicate IDs before inserting.
4. No unique constraints in `db/schema.sql` on the `policy` table beyond the primary key `id`.

**Conclusion:** Uploading the same PDF multiple times to `/analyze` is harmless — just burns LLM tokens and returns identical JSON. No rows created, no state changes. When automatic ingestion is wired up (plan → actual INSERTs), the pipeline will need `INSERT OR REPLACE` on `policy` and `INSERT OR IGNORE` on `organization`/`region` for idempotency.

---

## Session 13 — Mar 5, 2026

### Critique: extracted rules vs. PDF source (Acme Manufacturing HR-ATT-2024-001)

Compared the 50 rules inserted into the in-memory SQLite `rule` table against the actual policy PDF content. The pipeline successfully inserted 54 rows (1 org, 1 region, 1 junction, 1 policy, 50 rules) but the **rule quality has significant issues**.

#### What's correct

The core point values from Section 5.1 and 5.2 are accurately extracted:

| Rule | Extracted pts | PDF pts | Verdict |
| ---- | ------------- | ------- | ------- |
| ncns-first-day | +3.0 | 3.0 | Correct |
| ncns-each-consecutive-day | +3.0 | 3.0 | Correct |
| unexcused-full-day-absence | +1.5 | 1.5 | Correct |
| unexcused-half-day-absence | +1.0 | 1.0 | Correct |
| tardy-major | +1.0 | 1.0 | Correct |
| tardy-minor | +0.5 | 0.5 | Correct |
| early-departure-unauthorized | +1.0 | 1.0 | Correct |
| absence-on-holiday-critical-day | +2.0 | 2.0 | Correct |
| perfect-attendance-30-days | -0.5 | -0.5 | Correct |
| perfect-attendance-60-days | -1.0 | -1.0 | Correct |
| perfect-attendance-90-days | -1.5 | -1.5 | Correct |
| perfect-attendance-full-year | -2.0 | -2.0 | Correct |

#### Problem 1: Massive over-generation (50 rules vs. ~20 actual)

The PDF defines ~12 point-generating rules (Section 5.1), 4 perfect-attendance reductions (Section 5.2), 5 corrective action levels (Section 6), and 3 immediate-termination triggers. The LLM inflated this to 50 by turning procedural text, definitions, and administrative guidance into fake "rules":

| Hallucinated rule | Actually from |
| ----------------- | ------------- |
| `callout-procedure-rule` | Section 4.1 — a procedure, not a point rule |
| `occurrence-definition` | Section 3 — a definition |
| `rolling-12-month-window` | Section 3 — a definition |
| `notify-by-times-operator-setup` | Section 4 — shift schedule table |
| `supervisor-hris-coding-timeframe` | Section 9 — supervisor responsibility |
| `retention-audit-parameters` | Section 9 — record keeping |
| `documentation-deadlines-summary` | Section 7 — leave documentation |
| `overtime-voluntary-vs-mandatory-distinction` | Section 4.2 — narrative text |
| `temp-contract-worker-coverage` | Section 2 — scope statement |
| `perfect-attendance-certificate-tracking` | Duplicates the 90-day reward |
| `dispute-window-point-rebuttal` | Section 6 — employee right, not point-generating |
| `escalation-alerts-hr-vp` | Section 6 — HR involvement column, not a rule |
| `negative-balance-floor` | Policy constraint ("min balance is 0.0"), not a rule |
| `minimum-balance-enforcement` | Same constraint rephrased |

#### Problem 2: Corrective action levels misplaced as rules

Levels 1–5 are *consequences* triggered by point thresholds, not point-generating events. They belong in the `alert` table (which exists in the schema for this purpose), not in `rule`:

| Extracted rule | What it actually is |
| -------------- | ------------------- |
| `corrective-level-1` (pts=0.0, thr=3) | Level 1 consequence — Verbal Warning at 3.0–4.5 pts |
| `corrective-level-2` (pts=0.0, thr=5) | Level 2 consequence — Written Warning at 5.0–6.5 pts |
| `corrective-level-3` (pts=0.0, thr=7) | Level 3 consequence — Final Written Warning + 1-day suspension at 7.0–8.5 pts |
| `corrective-level-4` (pts=0.0, thr=9) | Level 4 consequence — Final Written Warning + 3-day suspension at 9.0–11.5 pts |
| `corrective-level-5` (pts=0.0, thr=12) | Level 5 consequence — Termination at 12.0+ pts |

#### Problem 3: Duplicate/redundant rules

- `mandatory-ot-no-show` (pts=+1.5) — Section 4.2 says "treated as unexcused absence", so this is the same as `unexcused-full-day-absence`, not a distinct rule
- `plant-shutdown-failure-to-return` (pts=+1.5) — Section 8.2 says "1.5-point unexcused absence", same duplication

#### Problem 4: Missing rules

- **Union Steward / Business leave** (Section 7, 0 pts) — not extracted
- **Inclement weather / Emergency Closure** (Section 8.3, 0 pts) — not extracted

#### Problem 5: Ambiguous semantics

- `third-minor-tardy-conversion` (pts=+1.0, thr=3) — PDF says "3rd minor tardy in same month = 1 full point". This is a reclassification (the 3 minor tardies get upgraded), not a flat additional point. The extracted rule is ambiguous about this.

#### Summary

| Category | Count |
| -------- | ----- |
| Correct point-generating rules | ~12 |
| Correct perfect-attendance reductions | 4 |
| Hallucinated / over-generated rules | ~28 |
| Corrective actions misplaced as rules | 5 |
| Administrative text wrongly made into rules | ~10 |

#### Prompt fix needed

The SQL generation / plan prompts need tighter guardrails:
- "Only create `rule` rows for items that **generate or reduce** attendance points"
- "Do NOT create `rule` rows for definitions, procedures, corrective action levels, or administrative responsibilities"
- "Corrective action levels (Section 6) belong in the `alert` table, not `rule`"
- "If a policy section says 'treated as [existing violation type]', do NOT create a separate rule — reference the existing one"

---

## Session 14 — Mar 5, 2026

### Fix: reduce rule over-generation from 50 to ~22 expected

Root cause identified: the `PLAN_SYSTEM_MSG` prompt explicitly instructed the LLM to create corrective-action trigger rules (group d), operational rule rows (rolling window, balance floor, occurrence definition), and used open-ended "and any other named in the policy" catch-alls that encouraged mining every section for rules.

#### Changes made

**1. `PLAN_SYSTEM_MSG` (cell `mpundg7z6lj`) — major rewrite**

- Rule table description changed from "one row per violation tier / escalation rule" to "one row per point-generating violation, approved-leave exemption, or perfect-attendance reduction. NOT for corrective action levels, definitions, or procedures."
- Reduced rule categories from 4 + operational to 3:
  - a. Violation/occurrence rules (points > 0) — kept
  - b. Approved-leave exemption rules (points = 0.0) — kept, capped to named leave types
  - c. Perfect-attendance reduction rules (points < 0) — kept
  - d. ~~Corrective-action trigger rules~~ — **removed entirely**
  - ~~Operational rule rows~~ — **removed entirely**
- Removed "and any other named in the policy" catch-all from groups a and b
- Added **RULE EXCLUSIONS** block — explicit list of 8 categories that must NOT become rule rows: definitions, call-out procedures, corrective action levels, immediate termination triggers, supervisor/HR responsibilities, operational parameters, scope statements, duplicate violations
- Added **EXPECTED RULE COUNT** guidance: "roughly 20–25 rule rows total. If your count exceeds 30, you are likely over-extracting."
- Added union steward/business leave to the named approved-leave list (was missing)
- Fixed `rule.threshold` description: added "unless the rule requires multiple events like third-minor-tardy = 3"

**2. `experiments/SQLGenPrompt.md` — RULE EXCLUSIONS section**

- Added `RULE EXCLUSIONS` section after `RULE ROWS` — mirrors the plan prompt exclusions as a second guardrail at the SQL generation stage
- Added instruction: "If the plan includes any of these in error, SKIP them and note the skip in your confidence deduction"
- Changed `RULE ROWS` to clarify: "Only generate rule rows that appear in the plan — do NOT invent additional rules"
- Removed "CA-triggers" from the points description (no longer a valid category)
- Added confidence penalty: "−0.10 if rule_count exceeds 30" and "−0.05 per rule row skipped because it matched a RULE EXCLUSION"

**3. Cell `9fef6d78` — post-INSERT validation guard**

Added a rule count sanity check after the rule detail printout:
- `> 30 rules`: WARNING about likely over-generation from definitions/procedures/corrective actions
- `< 10 rules`: WARNING about likely under-extraction of approved-leave exemptions or violation types
- `10–30 rules`: confirmation message that count is within expected range

#### Expected impact

| Category | Before | After |
| -------- | ------ | ----- |
| Violation rules (pts > 0) | 12 correct + 2 duplicates | ~10 (deduped) |
| Approved-leave (pts = 0) | 8 correct + ~14 hallucinated | ~9 (added union steward) |
| Perfect-attendance (pts < 0) | 4 correct | 4 |
| Corrective actions (misplaced) | 5 | 0 |
| Operational/admin (hallucinated) | ~20 | 0 |
| **Total** | **50** | **~22** |

#### Files modified

| File | Change |
| ---- | ------ |
| `experiments/01_pdf_to_db_query.ipynb` cell `mpundg7z6lj` | REPLACE — `PLAN_SYSTEM_MSG` rewritten with rule exclusions, expected count, tightened categories |
| `experiments/01_pdf_to_db_query.ipynb` cell `9fef6d78` | EDIT — added rule count sanity check (warning if >30 or <10) |
| `experiments/SQLGenPrompt.md` | EDIT — added RULE EXCLUSIONS section, confidence penalties, dedup instruction |
