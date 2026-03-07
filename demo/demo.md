# APPRENTICE

> **Capstone Project:** Building Agentic AI Applications with a Problem-First Approach
> **Team:** Ifesinachi Eze
> **Demo Date:** March 7, 2026

---

## USE CASE

**The Bottleneck:** Every enterprise runs on the same hidden workflow — someone reads a document, figures out what it means, and types the important parts into a system. HR reads a policy and enters attendance rules. Claims adjusters read medical records and enter coverage decisions. Procurement teams read contracts and enter vendor terms. It's skilled, tedious work — and it's the bottleneck of every organization.

**The AI Problem:** AI can read those documents. But AI doesn't give you the same answer twice. Ask it to extract rules from a policy today and you get one result. Ask tomorrow, you might get something slightly different. That's fine for writing emails. It's not fine when the output triggers someone's disciplinary action, denies an insurance claim, or commits your company to a vendor contract.

**Apprentice:** A framework that treats AI like an apprentice — it works under supervision, proves competence through measurement, and gradually earns autonomy. The AI reads documents, extracts structured data, proposes a plan, and waits for human sign-off. Trust is earned through measured performance, not declared.

**The Fair Play Initiative** is where we prove this works — starting with workforce attendance compliance, where the documents are complex (multi-page HR policies with nested rules and exceptions), the consequences are real (point accumulations trigger disciplinary action), and there's zero tolerance for error.

---

## SYSTEM DESIGN

### Business Constraints

- **Security:** SQL execution is locked to Playground mode only (SQLite sandbox). Production PostgreSQL deployments cannot execute AI-generated SQL. Playground can be reset/seeded at any time without risk.
- **Compliance:** Every pipeline step produces a reviewable artifact. Human ratings (Good / Partial / Bad) are persisted per step. Token usage, latency, and model identity logged to `AnalysisLog` for full traceability.
- **Cost:** Target under $0.05 per policy analysis (~$0.01–0.03 actual; as low as ~$0.005 with gemini-3-flash). No fine-tuned models — only prompt engineering, prompt distillation, and few-shot examples to maintain iteration speed and cost predictability.

### Iteration 1: Transparent Extraction Pipeline *(Black Box → Decomposed)*

- HR admin uploads a policy PDF/DOCX (or pastes text) to the system
- The LLM extracts keywords, generates a structured ingestion plan, and produces SQL — each as a separate, reviewable step
- HR reviews every step, rates each (Good / Partial / Bad), approves or rejects
- The system executes SQL only after human approval, in playground sandbox only
- Initially used GPT-5-mini — single-shot pipeline took 3–5 minutes per call with no way to swap models
- RAG evaluation: tested retrieval-augmented generation but found 97.3% of the document was retrieved — pure overhead for single-document extraction; full-text input used instead
- Arize AX observability added for tracing all LLM nodes

### Iteration 2: Database-Aware Reconciliation *(Stateful Pipeline)*

- LLM extracts and reconciles entities against existing DB records (catches typos, abbreviations, name variations)
- Deterministic conflict detection runs automatically (date overlaps, active-policy overwrites)
- Matched IDs flow downstream so plan and SQL reuse existing records instead of creating duplicates
- Human reviews flagged conflicts and reconciliation warnings before execution
- Per-step model configurators added to playground UI — discovered gemini-3-flash runs in a fraction of the time/cost vs GPT-5-mini
- Observability moved from external Arize AX into the UI — token badges, cost/latency per step, feedback ratings all visible inline
- Analytics persistence to Supabase PostgreSQL (replaces external logging)

### Iteration 3: Prompt Caching *(Cost Optimization at Scale)*

- OpenRouter prompt caching enabled across all LLM nodes — reuses cached system prompts, schema context, and planning guidance
- Cache hits on Plan and SQL steps reduce redundant token processing for repeated runs
- Lower per-run cost makes higher-volume batch processing economically viable
- Infrastructure step toward autonomous policy lifecycle (policy diffs, drift detection, audit reports)

---

## ITERATION TABLE

*Live production data from 71 analysis runs across 9 models (Supabase PostgreSQL)*

| Itr | Cost / Latency Factors | Optimizations | Guardrails | Eval Metrics |
|-----|----------------------|---------------|------------|--------------|
| **1** | 3 LLM calls per document (Extract → Plan → SQL); started with GPT-5-mini (~3–5 min/call); ~19K tokens | Meta-prompting, prompt distillation (Sonnet → gemini-flash), RAG evaluation (negative result — full-text beats retrieval), Arize AX observability | Human reviews 100%; rule exclusion guardrails (8 categories) | Keyword accuracy, plan–SQL alignment, per-step ratings |
| **2** | 4 LLM calls per document (+ reconciliation); ~31s with gemini-3-flash (down from ~3–5 min), ~21K tokens, ~$0.01–0.03/policy | Entity reconciliation (fuzzy matching), deterministic conflict detection, per-step model configurators (discovered gemini-flash = fraction of time/cost), analytics persistence | Playground/production isolation (AI-generated SQL sandboxed), reconciliation gate (0.7 confidence), conflict warnings, rollback on failure | Entity match accuracy, conflict detection rate, model rating % |
| **3** | 4 LLM calls + prompt caching on Plan/SQL steps; 23.5K tokens served from cache (5.5% of 427K total) | OpenRouter cache headers, cached prompt prefixes, batch processing | Same as Itr 2 | Cache hit rate, tokens saved, cost per policy |

---

## HOW THE ITERATIONS MAP TO THE TRUST LIFECYCLE

The experiment iterations (what we built) directly enable the trust phases (how the system behaves):

| Experiment Work | What It Built | Trust Phase It Enables |
|----------------|--------------|----------------------|
| **Itr 1:** Single-shot → decomposed pipeline (Extract → Plan → SQL), started with GPT-5-mini (3–5 min/call), prompt distillation, Arize AX observability, RAG evaluation (negative result) | Reviewable plan as verification gate, human feedback collection, token/cost tracking | **Phase 1 (Hands-On):** Human reviews everything, rates every step, system builds reliability baseline; feedback data accumulates for model comparison |
| **Itr 2:** Entity reconciliation (fuzzy org/policy matching against existing DB), conflict detection (date overlaps, active-policy overwrites), rule exclusion guardrails, confidence deduction rubric, playground/production isolation, per-step model configurators (discovered gemini-flash), enhanced annotations, analytics persistence | Database-aware pipeline that prevents duplicate entities, automated quality checks, model rating aggregation, per-step model comparison (GPT-5-mini → gemini-flash = fraction of time/cost), guardrails that catch data conflicts before human sees them | **Phase 2 (Building Trust):** High-confidence auto-approves; human reviews flagged items only; entity reconciliation prevents silent data corruption |
| **Itr 3:** Prompt caching across all LLM nodes, cache hit/write UI badges, cache metrics in analytics DB | Reduced redundant token processing for repeated runs; cost tracking infrastructure for cache savings | **Phase 2→3 transition:** Lower per-run cost makes higher-volume autonomous processing economically viable |
| **Future:** Policy diff detection, drift monitoring, batch processing | Autonomous policy lifecycle management | **Phase 3 (Autonomous):** Routine work flows through automatically; humans handle exceptions only |

---

## TRUST LIFECYCLE (3 PHASES)

### Phase 1 — Hands-On *(where we are today)*

- Human reviews every single output — extraction, plan, and SQL
- Rates each step: Good / Partial / Bad
- System builds a reliability baseline: "How often does the AI match the human?"
- Interface is the **workspace** — all reviews required before pipeline can proceed
- Approve button is locked until all steps are reviewed

### Phase 2 — Building Trust *(enabled by iteration 2–3 infrastructure)*

- High-confidence results (>90%) auto-approve
- Human reviews only what the system flags as uncertain
- Dashboard shows overnight processing summaries — confidence scores, flagged anomalies
- Interface becomes the **audit panel**
- Model comparison stats (% good/partial/bad per model per step) inform trust decisions

### Phase 3 — Autonomous *(future goal)*

- Only genuine edge cases reach a human — unusual documents, ambiguous language, cross-jurisdictional conflicts
- Everything routine is handled automatically
- Structured audit reports sent to compliance officers
- Drift detection catches when database state diverges from latest policy documents
- The human isn't removed — they're **promoted from data entry clerk to quality supervisor**

---

## APP GUARDRAILS — PLAYGROUND vs PRODUCTION

| Feature | Playground Mode (SQLite) | Production Mode (PostgreSQL) |
|---------|-------------------------|------------------------------|
| SQL execution | Enabled — run AI-generated SQL in sandbox | **Disabled** — 403 Forbidden |
| Reset all data | `POST /reset` — truncate all tables | **Disabled** |
| Seed demo data | `POST /seed` — load sample orgs, policies, employees | **Disabled** |
| Sample policies | 4 embedded policies for testing (Acme Manufacturing, NorthBridge Health, Horizon Retail) | Not available |
| Analysis pipeline | Full Extract → Plan → SQL with execution | Extract → Plan → SQL (review only, no execution) |
| Detection | Auto-detected from `DATABASE_URL` (sqlite:// = playground) | Auto-detected (postgresql:// = production) |
| SQL translation | SQLite syntax (INSERT OR IGNORE/REPLACE) | Auto-rewritten to PostgreSQL (ON CONFLICT DO NOTHING/UPDATE) |

---

## MODEL COMPARISON + FEEDBACK LOOP

### Per-Step Model Selection

Each pipeline step can use a different LLM model:

- **Step 1 (Extract):** `model_extract` parameter — keyword extraction is a classification task, cheaper models work well
- **Step 1b (Reconcile):** `model_reconcile` parameter — entity matching against existing DB; skipped (zero-cost) when DB is empty
- **Step 2 (Plan):** `model_plan` parameter — the verification gate, where quality matters most
- **Step 3 (SQL):** `model_sql` parameter — follows the plan, cheaper models sufficient

### Feedback Collection

After each analysis, the human rates every step:

- **Good** — extraction/plan matches the source document
- **Partial** — mostly correct, some gaps
- **Bad** — significant errors or hallucinations

Ratings stored in `AnalysisFeedback` table with: step, rating, llm_model, filename.

### Aggregated Model Stats

`GET /feedback/stats` returns per-model, per-step performance:

- % Good / % Partial / % Bad ratings
- Average token usage
- Average latency (ms)
- Total runs

This data is what makes the Phase 1 → Phase 2 transition possible: when a model consistently rates >90% Good on a step, that step can be auto-approved.

### Decomposition Strategy (proven technique)

Iteration 1 started as a single-shot black box — one LLM call that went from raw document to SQL. The output was impossible to verify: you could see the final SQL, but you had no way to know *why* the AI chose those tables, joins, or values.

**The fix: step-by-step decomposition into 3 transparent stages.**

| Step | Purpose | Artifact Produced | Why It Matters |
|------|---------|-------------------|----------------|
| **1. Extract** | Identify what the document contains | Keyword chips mapped to 8 schema categories | Human can verify "did the AI find the right things?" |
| **2. Plan** | Decide what to do with the extracted data | Structured ingestion plan — table-by-table INSERT steps, rule rows, confidence scores | **The verification gate** — a compliance officer can read and approve this before any SQL runs |
| **3. SQL** | Generate executable code from the plan | SQL INSERT statements following FK constraints | Follows the plan mechanically — cheaper models sufficient |

**Why decomposition works here:**

1. **Each step produces a reviewable artifact** — no more black boxes
2. **Each step can use a different model** — expensive models where quality matters (Plan), cheap models where the task is mechanical (Extract, SQL)
3. **The Plan step is the human checkpoint** — it separates "what did the AI understand?" from "what code will it generate?"
4. **Errors are localized** — if the SQL is wrong, you check the Plan. If the Plan is wrong, you check the Extraction. No need to debug a monolithic prompt.

This decomposition is what enabled every subsequent optimization: prompt distillation, per-step feedback, model comparison, and the trust lifecycle.

### Prompt Distillation (proven technique)

- Run a strong model (Claude Sonnet 4.6) once on the planning step — 36s, 12,164 tokens, confidence 0.87
- Extract the 6 structural reasoning patterns it discovered (INSERT order, ID chaining, rule granularity, value derivation, natural keys, existence checks)
- Encode those patterns as explicit guidance in cheaper models' system prompts
- Result: gemini-3-flash achieves same quality at ~40x cost reduction (15s, 8.3K tok, ~$0.003/run); gemini-3.1-flash-lite at ~120x reduction (7s, 8.6K tok, ~$0.001/run). No fine-tuning, no training data, instantly reversible

---

## KEY TECHNICAL INSIGHTS (poster talking points)

1. **Trust is earned, not declared.** You don't flip a switch and call the system reliable. You measure your way there — Phase 1 feedback is what makes Phase 3 possible. You can't skip to the end.

2. **The plan is the product.** The extraction and SQL are implementation details. The structured plan is what a compliance officer can actually read and approve. This is the verification gate.

3. **Prompt distillation > fine-tuning** for iteration speed. Run a strong model once, encode its reasoning into cheaper models' prompts. 40–120x cost reduction (Sonnet → gemini-flash), no training data, no GPU time, instantly reversible.

4. **Playground mode is not optional.** AI-generated SQL must never touch production without human approval. The sandbox/production split is a core architectural decision, not a convenience feature.

5. **RAG is not always the answer.** For exhaustive single-document extraction, full-text input beats retrieval. RAG retrieved 97.3% of the document = pure overhead. RAG adds value with multiple documents, not single-document extraction.

6. **The feedback loop closes the circle.** Human ratings → model comparison → confidence thresholds → progressive autonomy. Without the ratings infrastructure, there's no path from Phase 1 to Phase 3.

7. **Stateless pipelines corrupt shared databases.** An AI pipeline that doesn't know what's already in the database will silently create duplicates. Entity reconciliation — using the LLM's semantic understanding to match "ACMI Manufacturing Co" to "Acme Manufacturing Corporation" — is not optional for production use.

8. **LLMs fill blanks, they don't flag them.** When a source document is missing metadata (company name, region, effective date), the model fabricates plausible values instead of reporting the gap. Extraction prompts need explicit absence handling — instructions for what to do when data is *not there*, not just when it is. Without this, hallucinated dates, company names, or regions silently corrupt the database with realistic-looking but invented data.

---

## DEMO FLOW (suggested)

1. **Landing page** — show the Apprentice vision (Bottleneck → AI Problem → Solution)
2. **Old vs New** — manual form vs AI pipeline side-by-side (on the landing page)
3. **Upload a policy PDF** — show the 4-step pipeline in action
4. **Step 1 (Extract)** — keyword chips, model selector, per-step feedback buttons
5. **Step 1b (Reconcile)** — entity matches with confidence %, conflict warnings (date overlaps, duplicate policies)
6. **Step 2 (Plan)** — structured ingestion plan using matched IDs, confidence score, human review gate
7. **Step 3 (SQL)** — generated SQL with correct FK references, sandbox execution, results verification
8. **Playground mode** — reset, seed data, sample policies, safe testing
9. **Model stats** — show feedback aggregation, per-model rating percentages
10. **Trust lifecycle** — walk through Phase 1 → 2 → 3 using the landing page mockups
11. **Iteration journey** — poster diagram showing how experiments built the trust infrastructure
