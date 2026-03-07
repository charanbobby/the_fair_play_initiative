# APPRENTICE

> **Capstone Project:** Building Agentic AI Applications with a Problem-First Approach
> **Team:** Sricharan Sunkara, Pragyna Reddy
> **Demo Date:** March 7, 2026

---

## USE CASE

**The Bottleneck:** Every enterprise runs on the same hidden workflow — someone reads a document, figures out what it means, and types the important parts into a system. It's skilled, tedious work — and it's the bottleneck of every organization.

**The AI Problem:** AI can read those documents. But AI doesn't give you the same answer twice. That's fine for writing emails. It's not fine when the output triggers disciplinary action or denies an insurance claim.

**Apprentice:** A framework that treats AI like an apprentice — it works under supervision, proves competence through measurement, and gradually earns autonomy.

**The Fair Play Initiative** is where we prove this works — starting with workforce attendance compliance.

---

## SYSTEM DESIGN

### Business Constraints

- **Security:** SQL execution locked to Playground mode only (SQLite sandbox). Production PostgreSQL cannot execute AI-generated SQL.
- **Compliance:** Every step produces a reviewable artifact. Human ratings persisted per step. Token usage, latency, model identity logged for traceability.
- **Cost:** Target < $0.05 per policy (~$0.01–0.03 actual; as low as ~$0.005 with gemini-3-flash). No fine-tuned models — prompt engineering + distillation only.

### Iteration 1: Transparent Extraction Pipeline *(Black Box → Decomposed)*

- HR admin uploads a policy PDF/DOCX (or pastes text) to the system
- The LLM extracts keywords, generates a structured ingestion plan, and produces SQL — each as a separate, reviewable step
- HR reviews every step, rates each (Good / Partial / Bad), approves or rejects
- The system executes SQL only after human approval, in playground sandbox only
- Initially used GPT-5-mini — single-shot pipeline took 3–5 minutes per call with no way to swap models
- RAG evaluation: tested retrieval-augmented generation but found 97.3% of the document was retrieved — pure overhead for single-document extraction; full-text input used instead

### Iteration 2: Database-Aware Reconciliation *(Stateful Pipeline)*

- LLM extracts and reconciles entities against existing DB records (catches typos, abbreviations, name variations)
- Deterministic conflict detection runs automatically (date overlaps, active-policy overwrites)
- Matched IDs flow downstream so plan and SQL reuse existing records instead of creating duplicates
- Human reviews flagged conflicts and reconciliation warnings before execution
- Per-step model configurators added to playground UI — swap models per step to compare quality/cost
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
| **1** | 3 LLM calls per document (Extract → Plan → SQL); started with GPT-5-mini (~3–5 min/call); ~19K tokens | Meta-prompting, prompt distillation (Sonnet → gemini-flash), RAG evaluation (negative result — full-text beats retrieval) | Human reviews 100%; rule exclusion guardrails (8 categories) | Keyword accuracy, plan–SQL alignment, per-step ratings |
| **2** | 4 LLM calls per document (+ reconciliation); ~31s with gemini-3-flash (down from ~3–5 min), ~21K tokens, ~$0.01–0.03/policy | Entity reconciliation (fuzzy matching), deterministic conflict detection, per-step model configurators (discovered gemini-flash = fraction of time/cost), analytics persistence | Playground/production isolation (AI-generated SQL sandboxed), reconciliation gate (0.7 confidence), conflict warnings, rollback on failure | Entity match accuracy, conflict detection rate, model rating % |
| **3** | 4 LLM calls + prompt caching on Plan/SQL steps; 23.5K tokens served from cache (5.5% of 427K total) | OpenRouter cache headers, cached prompt prefixes, batch processing | Same as Itr 2 | Cache hit rate, tokens saved, cost per policy |

### Production Stats (from Supabase `analysis_logs` — 71 runs, 9 models)

| Step | Model | Runs | Avg Tokens | Avg Latency | Feedback |
|------|-------|------|-----------|-------------|----------|
| Extract | gemini-3-flash | 11 | 2,160 | 4.9s | 5 Good, 1 Bad |
| Extract | gemini-3.1-flash-lite | 4 | 2,236 | 3.3s | 3 Good |
| Extract | gpt-5-mini | 5 | 4,787 | 63.3s | 4 Good |
| Plan | claude-sonnet-4.6 | 1 | 12,164 | 36.1s | — |
| Plan | deepseek-v3.2 | 1 | 15,106 | 112.8s | 1 Good |
| Plan | gemini-3-flash | 12 | 8,339 | 15.4s | 2 Good |
| Plan | gemini-3.1-flash-lite | 4 | 8,568 | 7.2s | 4 Good, 1 Partial |
| Plan | gpt-5-mini | 2 | 13,663 | 123.5s | — |
| Reconcile | gemini-3-flash | 7 | 1,475 | 3.5s | 3 Good, 1 Bad |
| Reconcile | gemini-3.1-flash-lite | 1 | 1,559 | 2.4s | — |
| Reconcile | gpt-4o-mini | 4 | 1,736 | 6.2s | — |
| Reconcile | gpt-5.4 | 1 | 1,625 | 2.3s | — |
| SQL | claude-sonnet-4.6 | 1 | 10,601 | 18.8s | — |
| SQL | gemini-3-flash | 11 | 7,424 | 6.8s | 2 Good |
| SQL | gemini-3.1-flash-lite | 1 | 7,772 | 4.5s | — |
| SQL | gemini-3.1-pro | 2 | 14,723 | 79.1s | 1 Good, 1 Bad |
| SQL | devstral-2512 | 1 | 8,959 | 15.3s | 1 Good |
| SQL | gpt-5-mini | 2 | 11,284 | 68.3s | — |

### Prompt Caching Results

| Metric | Value |
|--------|-------|
| Total runs (all cache-enabled) | 71 |
| Runs with cache hits | 6 (plan: 3, sql: 3) — only steps with prompts above provider minimum size |
| Total tokens served from cache | 23,553 |
| Total tokens processed | 427,039 |
| Cache hit token ratio | 5.5% |
| Latency (cache hit vs miss) | Mixed — hit rate expected to improve with higher run volume on same model/step combinations |

---

## ITERATION DIAGRAMS

### Iteration 1 — Decomposed Pipeline *(Black Box → Decomposed)*

```text
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │   Step 1:    │    │   Step 2:    │    │   Step 3:    │
│  Upload      │───▶│   EXTRACT   │───▶│   PLAN       │───▶│   SQL        │
│  Policy PDF  │    │             │    │             │    │             │
│              │    │  GPT-5-mini │    │  GPT-5-mini │    │  GPT-5-mini │
└──────────────┘    │  (~1 min)   │    │  (~2 min)   │    │  (~1 min)   │
                    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                           │                  │                  │
                    ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
                    │   Human     │    │   Human     │    │   Human     │
                    │   Review    │    │   Review    │    │   Review    │
                    │   G / P / B │    │   G / P / B │    │   G / P / B │
                    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                           │                  │                  │
                           └──────────────────┼──────────────────┘
                                              │
                                       ┌──────▼──────┐
                                       │ Audit Logger│
                                       │ (Arize AX)  │
                                       └─────────────┘

  Started as 1 LLM call (black box, 3–5 min total) — decomposed
  into 3 steps because single-shot output was opaque and impossible
  to verify. No model swapping — locked to GPT-5-mini.
```

**Prompt Distillation:**

```text
┌───────────────────┐       ┌────────────────────────┐       ┌───────────────────┐
│  Claude Sonnet    │ gold  │   Extract 6 structural │inject │   gemini-3-flash  │
│  4.6              │──────▶│   reasoning patterns   │──────▶│   + PLANNING      │
│  (one-time run)   │ plan  │   (INSERT order, ID    │ into  │   GUIDANCE block  │
│                   │       │   chaining, rule gran-  │prompt │                   │
│  36s, 12K tok     │       │   ularity, natural keys)│      │  Same quality,    │
│  ~$0.12/run       │       │                        │       │  40–120x cheaper  │
└───────────────────┘       └────────────────────────┘       └───────────────────┘
```

### Iteration 2 — Entity Reconciliation + Guardrails *(Stateful Pipeline)*

```text
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │   Step 1:    │    │  Step 1b:    │    │   Step 2:    │    │   Step 3:    │
│  Upload      │───▶│   EXTRACT   │───▶│  RECONCILE   │───▶│   PLAN       │───▶│   SQL        │
│  Policy PDF  │    │             │    │  (NEW)       │    │             │    │             │
│              │    │  gemini-3   │    │  gemini-3   │    │  gemini-3   │    │  gemini-3   │
└──────────────┘    │  flash ~5s  │    │  flash ~4s  │    │  flash ~15s │    │  flash ~7s  │
                    │  + rule     │    │  fuzzy match │    │  + matched  │    │  + sandbox  │
                    │  exclusions │    │  vs existing │    │  IDs from   │    │  execution  │
                    └──────┬──────┘    │  DB records  │    │  reconcile  │    └──────┬──────┘
                           │           └──────┬──────┘    └──────┬──────┘           │
                           │           ┌──────▼──────┐          │                  │
                           │           │  Conflict   │          │                  │
                           │           │  Detection  │          │                  │
                           │           │  (date over-│          │                  │
                           │           │  laps, dupes)│         │                  │
                           │           └─────────────┘          │                  │
                           └────────────────────────────────────┼──────────────────┘
                                                                │
                                                    ┌───────────▼───────────┐
                                                    │  Human-in-the-Loop   │
                                                    │  Approval            │
                                                    │  + Model Selectors   │
                                                    └───────────┬──────────┘
                                                                │
                                                    ┌───────────▼───────────┐
                                                    │  In-UI Observability  │
                                                    │  (replaces Arize AX)  │
                                                    │  Token badges, cost,  │
                                                    │  latency, feedback    │
                                                    │  ratings, analytics   │
                                                    │  → Supabase Postgres  │
                                                    └──────────────────────┘

  Observability moved from external Arize AX into the UI — token
  badges, cost/latency per step, feedback ratings, all persisted
  to Supabase PostgreSQL. Model configurators enabled swapping
  GPT-5-mini → gemini-3-flash (~31s total, down from ~3–5 min).
  Entity reconciliation prevents duplicate orgs/policies.
```

### Iteration 3 — Prompt Caching *(Cost Optimization at Scale)*

```text
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │   EXTRACT    │    │  RECONCILE   │    │   PLAN       │    │   SQL        │
│  Upload      │───▶│             │───▶│             │───▶│             │───▶│             │
│  Policy PDF  │    │  ~2K tokens │    │  ~1.5K tok  │    │  ~8K tokens │    │  ~7K tokens │
│              │    │  (below     │    │  (below     │    │  (CACHE     │    │  (CACHE     │
└──────────────┘    │  cache min) │    │  cache min) │    │  ELIGIBLE)  │    │  ELIGIBLE)  │
                    └─────────────┘    └─────────────┘    └──────┬──────┘    └──────┬──────┘
                                                                 │                  │
                                                          ┌──────▼──────────────────▼──────┐
                                                          │  Cached prompt prefixes:       │
                                                          │  System prompt + schema JSON   │
                                                          │  + planning guidance           │
                                                          │                                │
                                                          │  23.5K tokens from cache       │
                                                          │  (5.5% of 427K total)          │
                                                          │  Hit rate grows with volume    │
                                                          └───────────────────────────────┘

  OpenRouter cache headers on all LLM nodes. Only Plan + SQL
  steps have prompts large enough for cache eligibility.
```

---

## TRUST LIFECYCLE

| Phase | Human Role | System Behavior | Interface |
|-------|-----------|-----------------|-----------|
| **1 — Hands-On** *(today)* | Reviews every output, rates each step G/P/B | Builds reliability baseline | Workspace — approve locked until all reviewed |
| **2 — Building Trust** | Reviews flagged items only | High-confidence auto-approves; model stats inform trust | Audit panel — overnight summaries |
| **3 — Autonomous** | Handles exceptions only | Routine flows automatically; drift detection; audit reports | Quality supervisor — promoted from data entry |

**Key insight:** Phase 1 feedback is what makes Phase 3 possible. You can't skip to the end.

---

## KEY INSIGHTS

1. **Trust is earned, not declared.** You measure your way there.
2. **The plan is the product.** It's the verification gate a compliance officer can read.
3. **Prompt distillation > fine-tuning.** Same quality, 40–120x cost reduction (Sonnet → gemini-flash), instantly reversible.
4. **Playground mode is not optional.** AI-generated SQL must never touch production.
5. **RAG is not always the answer.** For single-document extraction, full-text beats retrieval (97.3% retrieved = pure overhead).
6. **The feedback loop closes the circle.** Ratings → comparison → thresholds → autonomy.
7. **Stateless pipelines corrupt shared databases.** Entity reconciliation prevents duplicate orgs/policies from accumulating silently.
8. **LLMs fill blanks, they don't flag them.** When a source document is missing metadata (company name, region, effective date), the model fabricates plausible values instead of reporting the gap. Extraction prompts need explicit absence handling — instructions for what to do when data is *not there*, not just when it is. In a compliance system, a hallucinated date or company name silently corrupts the database.
