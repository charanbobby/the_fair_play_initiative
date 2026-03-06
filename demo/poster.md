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
| **1** | 1 LLM call; single-shot extract+SQL; **black box** — opaque SQL, hard to verify what the AI decided | Meta-prompting (ChatGPT Playground, multi-shot samples) to define structured output shape + SQL plan templates; Pydantic models via `litellm + instructor` | Human reviews 100%; playground-only | Keyword accuracy, SQL validity, confidence |
| **2** | 3 LLM calls — **decomposed because Itr 1 was a black box** (opaque SQL, no way to verify AI reasoning); **Extract:** ~10s/2.5K tok (gpt-4o-mini), ~31s/4.3K tok (gpt-5-mini); **Plan:** ~64s/9.5K tok (gpt-4o-mini), ~105s/13.3K tok (gpt-5-mini); **SQL:** ~52s/9.3K tok (gpt-5-mini) | Prompt distillation (Sonnet 4.6 → gpt-5-mini); per-step model selectors; **plan as verification gate**; **RAG experiment (negative result):** ChromaDB retrieval retrieved 97.3% of document (20/26 chunks), added 1.8x latency (584.8s vs 316.7s) and +80% tokens (64.6K vs 36K) — pure overhead for single-document exhaustive extraction. Full-text input is the right approach here; RAG adds value only for multi-document querying. | Human review at plan stage; rule exclusion guardrails (8 categories); rule count bounds (10–30); confidence deduction rubric | Rule count vs expected, plan–SQL alignment, per-step ratings, tokens per model per step |
| **3** | 3 calls + feedback routing; **Full pipeline:** ~188s, ~27K tokens, < $0.01 per policy | Feedback loop: human ratings → model comparison → confidence thresholds; aggregated rating stats per model per step | Rule exclusion guardrails; confidence deduction rubric; playground/production mode isolation; rollback on SQL failure | Model rating % (good/partial/bad), cost per policy, time-to-ingest |

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

### Iteration 1 — Single-Shot Pipeline (Black Box)

**The challenge:** We gave the AI a document and a prompt. It produced SQL that added tables and rules — but validating each table was extremely difficult. The output was a black box: you could see the final SQL, but you had no way to verify *why* the AI chose those tables, joins, or values. No way to catch logic errors before execution.

**Meta-prompting (ChatGPT Playground):** Used multi-shot samples to define (1) the Pydantic structured output shape (per-table keyword fields), and (2) the human-readable SQL plan template format. Fed multiple example policies to the LLM and iterated on the prompt templates that would later guide extraction and planning.

**This led to the key insight:** we need to decompose the pipeline so the AI shows its reasoning at each step.

```
┌──────────┐     ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐     ┌──────────┐     ┌──────────┐
│  Upload  │────▶  ██████████████████████ ────▶│  Human   │────▶│ Sandbox  │
│  Policy  │     │ ██  BLACK BOX  ██████ │     │  Review  │     │ Execute  │
└──────────┘      ██  1 LLM call  ██████       │          │     └──────────┘
                 │ ██  Extract+SQL █████ │     │ Can see  │      SQLite only
                  ██  (opaque)    ██████       │ output,  │
                 │ ██████████████████████ │     │ can't    │
                  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─      │ verify   │
                  litellm + instructor         │ reasoning│
                  Pydantic structured output   └──────────┘

  Problem: Human reviews SQL but has no visibility into
  WHY the AI chose these tables, joins, or values.
  ──────────────────────────────────────────────────────
  ➜ Solution: Decompose into 3 transparent steps (Itr 2)
```

### Iteration 2 — Decomposed Pipeline (Transparent)

**Why decompose?** Itr 1's black box produced opaque SQL. By splitting into Extract → Plan → SQL, each step produces a **reviewable artifact**. The Plan step is the key — it's a human-readable ingestion plan that a compliance officer can verify before any SQL runs.

**Still challenging:** Even with decomposition, validating each extraction and every SQL rule the AI generates remained difficult. A single policy can produce 20–30 rules across multiple tables — manually checking each one is time-consuming. This drove us to Iteration 3: give the administrator a safe place to actually *run* the output and see the results.

**RAG experiment (negative result):** Tried ChromaDB vector retrieval to replace brute-force text truncation. Result: retrieved 97.3% of the document (20 of 26 chunks), 1.8x slower (584.8s vs 316.7s), +80% more tokens (64.6K vs 36K). For single-document exhaustive extraction, the LLM needs the entire policy — RAG is pure overhead. RAG would add value for cross-policy querying (50+ policies) or when documents exceed the context window.

```
┌──────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│  Upload  │────▶│  Step 1   │────▶│  Step 2   │────▶│  Step 3   │
│  Policy  │     │  EXTRACT  │     │   PLAN    │     │    SQL    │
│  (PDF/   │     │  "I found │     │  "I'll    │     │  "Here's  │
│  DOCX/   │     │   these   │     │   do      │     │   the     │
│  text)   │     │   rules"  │     │   this"   │     │   code"   │
└──────────┘     │           │     │           │     │           │
                 │ gpt-4o-   │     │ gpt-5-   │     │ gpt-5-   │
                 │ mini      │     │ mini      │     │ mini      │
                 │ ~10s      │     │ ~105s     │     │ ~52s      │
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

  Prompt Distillation — cost savings:
  ┌─────────────────────────────────────────────────────────────┐
  │  Sonnet 4.6 (plan step):  90s, 14,920 tok, ~$0.12/run     │
  │  gpt-5-mini (plan step): 105s, 13,337 tok, ~$0.01/run     │
  │                                                             │
  │  How: Run Sonnet once → extract 6 structural reasoning     │
  │  patterns (INSERT order, ID chaining, rule granularity,    │
  │  value derivation, natural keys, existence checks) →       │
  │  encode as PLANNING GUIDANCE in gpt-5-mini's system prompt │
  │                                                             │
  │  Result: ~12x cost reduction, same output quality,         │
  │  no fine-tuning, no training data, instantly reversible    │
  └─────────────────────────────────────────────────────────────┘

  RAG Experiment (REJECTED):
  ┌────────────┐     ┌────────────┐     ┌────────────┐
  │ ChromaDB   │────▶│ Retrieve   │────▶│ Feed to    │
  │ embed 26   │     │ 20 chunks  │     │ LLM        │
  │ chunks     │     │ (97.3%)    │     │            │
  └────────────┘     └────────────┘     └────────────┘
  Result: 584.8s, 64.6K tokens — 1.8x slower, +80% tokens
  Reason: exhaustive extraction needs the full document
```

### Iteration 3 — Playground + Guardrails *(where we are today)*

**The problem from Itr 2:** Decomposition made the AI's reasoning visible, but validating every extracted rule across 20–30 rows was still hard. How do you know the rules are correct without seeing them in action?

**The solution:** Give the policy administrator a **playground** — a sandbox SQLite database they can reset, seed with sample data, and execute AI-generated SQL against without touching production. They upload a policy, review the plan, approve it, and *see how the rules actually affect the system*. If something's wrong, reset and try again. Production (PostgreSQL) blocks all AI-generated SQL execution — 403 Forbidden.

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
               │     Human still reviews 100% (Phase 1)        │
               │     But system now collects:                   │
               │       • Per-step ratings (G/P/B)              │
               │       • Per-model token usage + latency       │
               │       • Aggregated model stats via /stats     │
               │                                               │
               │     When enough data accumulates:             │
               │         ┌──────────┴──────────┐               │
               │         │                     │               │
               │    ▼ > 90% Good           ▼ < 90%             │
               │  ┌──────────┐       ┌──────────────┐         │
               │  │  Future: │       │  Continue    │         │
               │  │  Auto-   │       │  Human      │         │
               │  │  approve │       │  Review     │         │
               │  └──────────┘       └──────────────┘         │
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
