# APPRENTICE

> **Capstone Project:** Building Agentic AI Applications with a Problem-First Approach
> **Team:** Ifesinachi Eze
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
- **Cost:** Target < $0.01 per policy. No fine-tuned models — prompt engineering + distillation only.

### Template 1: Supervised Pipeline *(High Control, Low Agency)*

Upload → LLM extracts → LLM plans → Human reviews & rates every step → Human approves → SQL runs in sandbox

### Template 2: Confidence-Routed Pipeline *(Medium Control, Medium Agency)*

Same pipeline → High-confidence (>90%) auto-approves → Human reviews flagged items only

### Template 3: Autonomous Policy Lifecycle *(Low Control, High Agency)*

LLM reads policy revisions → diffs against existing rules → updates autonomously → sends audit reports → flags drift

---

## ITERATION TABLE

*Live production data from 27 analysis runs (Supabase PostgreSQL)*

| Itr | Cost / Latency | Optimizations | Guardrails | Eval Metrics |
|-----|---------------|---------------|------------|--------------|
| **1** | 1 LLM call; single-shot extract+SQL | Meta-prompting; Pydantic structured output | Human reviews 100%; playground-only | Keyword accuracy, SQL validity, confidence |
| **2** | 3 LLM calls; **Extract:** ~10s/2.5K tokens (gpt-4o-mini), ~31s/4.3K tokens (gpt-5-mini); **Plan:** ~64s/9.5K tokens (gpt-4o-mini), ~105s/13.3K tokens (gpt-5-mini); **SQL:** ~52s/9.3K tokens (gpt-5-mini) | Prompt distillation (Sonnet 4.6 → gpt-5-mini); per-step model selectors; plan as verification gate | Human review at plan stage; rule exclusion guardrails (8 categories); rule count bounds (10–30); confidence deduction rubric | Rule count vs expected, plan–SQL alignment, per-step ratings, tokens per model per step |
| **3** | 3 calls + feedback routing; **Full pipeline:** ~188s, ~27K tokens, < $0.01 per policy | Feedback loop → model comparison → confidence thresholds | Auto-approve >90% confidence; playground/production isolation; rollback on SQL failure | Model rating % (good/partial/bad), cost per policy, drift detection |

### Production Model Stats (from Supabase `analysis_logs`)

| Step | Model | Runs | Avg Tokens | Avg Latency | Feedback |
|------|-------|------|-----------|-------------|----------|
| Extract | gpt-4o-mini | 4 | 2,496 | 10.1s | — |
| Extract | gpt-5-mini | 8 | 4,309 | 31.4s | 4 Good |
| Plan | gpt-4o-mini | 4 | 9,476 | 63.6s | — |
| Plan | gpt-5-mini | 8 | 13,337 | 105.2s | 2 Good |
| SQL | gpt-5-mini | 3 | 9,282 | 52.3s | 1 Bad |

---

## ITERATION DIAGRAMS

### Iteration 1 — Single-Shot Pipeline

```
┌──────────┐     ┌─────────────────────┐     ┌──────────┐     ┌──────────┐
│  Upload  │────▶│  LLM: Extract + SQL │────▶│  Human   │────▶│ Sandbox  │
│  Policy  │     │  (1 call)           │     │  Review  │     │ Execute  │
└──────────┘     └─────────────────────┘     └──────────┘     └──────────┘
                  litellm + instructor                         SQLite only
                  Pydantic structured output
```

### Iteration 2 — Decomposed Pipeline with Model Routing

```
┌──────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│  Upload  │────▶│  Step 1   │────▶│  Step 2   │────▶│  Step 3   │
│  Policy  │     │  EXTRACT  │     │   PLAN    │     │    SQL    │
│  (PDF/   │     │           │     │           │     │           │
│  DOCX/   │     │ gpt-4o-   │     │ gpt-5-   │     │ gpt-5-   │
│  text)   │     │ mini      │     │ mini      │     │ mini      │
└──────────┘     │ ~10s      │     │ ~105s     │     │ ~52s      │
                 │ 2.5K tok  │     │ 13.3K tok │     │ 9.3K tok  │
                 └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                       │                 │                  │
                 ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
                 │  Human    │     │  Human    │     │  Human    │
                 │  Rate:    │     │  Rate:    │     │  Rate:    │
                 │  G / P / B│     │  G / P / B│     │  G / P / B│
                 └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                       │                 │                  │
                       ▼                 ▼                  ▼
                 ┌─────────────────────────────────────────────┐
                 │          AnalysisLog + AnalysisFeedback     │
                 │  (tokens, latency, model, rating per step)  │
                 └─────────────────────────────────────────────┘

  Prompt Distillation: Sonnet 4.6 (90s, 14.9K tok) → encode 6 reasoning
  patterns → gpt-5-mini gets same quality at 1/10th cost
```

### Iteration 3 — Confidence-Routed with Guardrails

```
┌──────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│  Upload  │────▶│  EXTRACT  │────▶│   PLAN    │────▶│    SQL    │
│  Policy  │     │ + guardrails     │ + confidence    │ + validation
└──────────┘     └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                       │                 │                  │
                 ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
                 │ 8-category│     │ Confidence │     │ Playground│
                 │ rule      │     │ deduction  │     │ vs Prod   │
                 │ exclusion │     │ rubric     │     │ isolation │
                 └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                       │                 │                  │
                       ▼                 ▼                  ▼
               ┌───────────────────────────────────────────────┐
               │              Confidence Score                  │
               │                    │                           │
               │         ┌──────────┴──────────┐               │
               │         │                     │               │
               │    ▼ > 90%                ▼ < 90%             │
               │  ┌──────────┐       ┌──────────────┐         │
               │  │  Auto-   │       │  Flag for    │         │
               │  │  approve │       │  Human Review│         │
               │  └──────────┘       └──────────────┘         │
               │                                               │
               │  Feedback Loop:                               │
               │  ratings → model stats → thresholds → trust   │
               └───────────────────────────────────────────────┘
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
3. **Prompt distillation > fine-tuning.** Same quality, 1/10th cost, instantly reversible.
4. **Playground mode is not optional.** AI-generated SQL must never touch production.
5. **RAG is not always the answer.** For single-document extraction, full-text beats retrieval (97.3% retrieved = pure overhead).
6. **The feedback loop closes the circle.** Ratings → comparison → thresholds → autonomy.
