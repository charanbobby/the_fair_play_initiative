# APPRENTICE

> **Capstone Project:** Building Agentic AI Applications with a Problem-First Approach
> **Team:** Sricharan Sunkara, Pragyna Reddy
> **Demo Date:** March 7, 2026

*Poster design adapted from AI Employee Access Manager template (Canvas)*

---

## THE PROBLEM

Every enterprise runs on the same hidden workflow: someone reads a document, figures out what it means, and types the important parts into a system. It's skilled, tedious work — and it's the bottleneck of every organization.

AI can read those documents — but it doesn't give you the same answer twice. That's fine for emails. It's not fine when the output triggers disciplinary action or denies an insurance claim.

---

## THE SOLUTION

**Apprentice** treats AI like an apprentice — it works under supervision, proves competence through measurement, and gradually earns autonomy.

**The Fair Play Initiative** is where we prove this works — starting with workforce attendance compliance.

---

## PIPELINE ARCHITECTURE

### Iteration 1 — Decomposed Pipeline

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

  Started as 1 LLM call (black box) — decomposed
  into 3 steps because single-shot output was opaque and impossible
  to verify. No model swapping — locked to GPT-5-mini.
```

### Prompt Distillation

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

### Iteration 2 — Entity Reconciliation + Guardrails

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
```

### Iteration 3 — Prompt Caching

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
```

---

## PRODUCTION STATS

*71 analysis runs across 9 models (Supabase PostgreSQL)*

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

### Prompt Caching

| Metric | Value |
|--------|-------|
| Total runs (all cache-enabled) | 71 |
| Runs with cache hits | 6 (plan: 3, sql: 3) |
| Total tokens served from cache | 23,553 |
| Total tokens processed | 427,039 |
| Cache hit token ratio | 5.5% |

---

## ITERATION SUMMARY

| Itr | What Changed | Key Result |
|-----|-------------|------------|
| **1** | Black box → 3-step decomposed pipeline; GPT-5-mini only; RAG tested and rejected | Each step reviewable; human rates G/P/B; Arize AX tracing |
| **2** | + Entity reconciliation; per-step model selectors; in-UI observability | 31s total (down from 3–5 min); ~$0.01–0.03/policy; conflict detection |
| **3** | + Prompt caching on Plan/SQL steps | 23.5K tokens from cache; lower cost at scale |

---

## TRUST LIFECYCLE

| Phase | Human Role | System Behavior | Interface |
|-------|-----------|-----------------|-----------|
| **1 — Hands-On** *(today)* | Reviews every output, rates each step G/P/B | Builds reliability baseline | Workspace — approve locked until all reviewed |
| **2 — Building Trust** | Reviews flagged items only | High-confidence auto-approves; model stats inform trust | Audit panel — overnight summaries |
| **3 — Autonomous** | Handles exceptions only | Routine flows automatically; drift detection; audit reports | Quality supervisor — promoted from data entry |

---

## KEY INSIGHTS

1. **Trust is earned, not declared.** You measure your way there.
2. **The plan is the product.** It's the verification gate a compliance officer can read.
3. **Prompt distillation > fine-tuning.** 40–120x cost reduction, instantly reversible.
4. **Playground mode is not optional.** AI-generated SQL must never touch production.
5. **RAG is not always the answer.** 97.3% retrieved = pure overhead for single-document extraction.
6. **The feedback loop closes the circle.** Ratings → comparison → thresholds → autonomy.
7. **Stateless pipelines corrupt shared databases.** Entity reconciliation is not optional.
8. **LLMs fill blanks, they don't flag them.** Extraction prompts need explicit absence handling.