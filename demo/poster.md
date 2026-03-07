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

### Template 1: Supervised Pipeline *(High Control, Low Agency)*

Upload → LLM extracts → LLM plans → Human reviews & rates every step → Human approves → SQL runs in sandbox

### Template 2: Confidence-Routed Pipeline *(Medium Control, Medium Agency)*

Same pipeline → High-confidence (>90%) auto-approves → Human reviews flagged items only

### Template 3: Autonomous Policy Lifecycle *(Low Control, High Agency)*

LLM reads policy revisions → diffs against existing rules → updates autonomously → sends audit reports → flags drift

---

## ITERATION TABLE

*Live production data from 43 analysis runs across 7+ models (Supabase PostgreSQL)*

| Itr | Cost / Latency | Optimizations | Guardrails | Eval Metrics |
|-----|---------------|---------------|------------|--------------|
| **1** | 1 LLM call; single-shot extract+SQL; **black box** — opaque SQL, hard to verify what the AI decided | Meta-prompting (ChatGPT Playground, multi-shot samples) to define structured output shape + SQL plan templates; Pydantic models via `litellm + instructor` | Human reviews 100%; playground-only | Keyword accuracy, SQL validity, confidence |
| **2** | 3 LLM calls — **decomposed because Itr 1 was a black box** (opaque SQL, no way to verify AI reasoning); **Extract:** ~3s/2.2K tok (gemini-3.1-flash-lite), ~5s/2.8K tok (gemini-3-flash), ~63s/4.8K tok (gpt-5-mini); **Plan:** ~7s/8.6K tok (gemini-3.1-flash-lite), ~16s/9K tok (gemini-3-flash), ~124s/13.7K tok (gpt-5-mini); **SQL:** ~6s/7.5K tok (gemini-3-flash), ~68s/11.3K tok (gpt-5-mini) | Prompt distillation (Sonnet 4.6 → gpt-5-mini); per-step model selectors; **plan as verification gate**; **RAG experiment (negative result):** ChromaDB retrieval retrieved 97.3% of document (20/26 chunks), added 1.8x latency (584.8s vs 316.7s) and +80% tokens (64.6K vs 36K) — pure overhead for single-document exhaustive extraction. Full-text input is the right approach here; RAG adds value only for multi-document querying. | Human review at plan stage; rule exclusion guardrails (8 categories); rule count bounds (10–30); confidence deduction rubric | Rule count vs expected, plan–SQL alignment, per-step ratings, tokens per model per step |
| **3** | 4 calls (+ reconciliation); **Full pipeline:** ~31s/~21K tokens (gemini-3-flash), ~258s/~31K tokens (gpt-5-mini), ~$0.01–0.03 per policy | Feedback loop: human ratings → model comparison → confidence thresholds; **Entity reconciliation:** LLM-powered fuzzy matching of orgs/policies/regions against existing DB records (handles typos, abbreviations, name variations); deterministic conflict detection (date overlaps, active-policy overwrites); **Prompt refinement:** killed `[PLACEHOLDER]` passthrough, few-shot SQL example, field semantics, self-validation checklist; **Multi-model evaluation:** 7+ models tested (Gemini, GPT, Claude, DeepSeek, Mistral) | Rule exclusion guardrails; confidence deduction rubric; playground/production mode isolation; rollback on SQL failure; entity reconciliation gate (0.7 confidence threshold); conflict warnings before execution | Model rating %, cost per policy, time-to-ingest, placeholder leak rate (0%), entity match accuracy, false-positive rate |

### Production Model Stats (from Supabase `analysis_logs` — 43 runs, 7+ models)

| Step | Model | Runs | Avg Tokens | Avg Latency | Feedback |
|------|-------|------|-----------|-------------|----------|
| Extract | gemini-3-flash | 4 | 2,813 | 4.9s | 3 Good, 1 Bad |
| Extract | gemini-3.1-flash-lite | 4 | 2,236 | 3.3s | 3 Good |
| Extract | gpt-5-mini | 5 | 4,787 | 63.3s | 4 Good |
| Plan | claude-sonnet-4.6 | 1 | 12,164 | 36.1s | — |
| Plan | deepseek-v3.2 | 1 | 15,106 | 112.8s | 1 Good |
| Plan | gemini-3-flash | 5 | 8,998 | 15.7s | 2 Good |
| Plan | gemini-3.1-flash-lite | 4 | 8,568 | 7.2s | 4 Good, 1 Partial |
| Plan | gpt-5-mini | 2 | 13,663 | 123.5s | — |
| Reconcile | gemini-3-flash | 1 | 1,484 | 3.1s | 1 Good |
| Reconcile | gpt-4o-mini | 4 | 1,736 | 6.2s | — |
| Reconcile | gpt-5.4 | 1 | 1,625 | 2.3s | — |
| SQL | claude-sonnet-4.6 | 1 | 10,601 | 18.8s | — |
| SQL | gemini-3-flash | 5 | 7,504 | 6.4s | 2 Good |
| SQL | gemini-3.1-flash-lite | 1 | 7,772 | 4.5s | — |
| SQL | gemini-3.1-pro | 1 | 18,543 | 102.4s | 1 Good |
| SQL | devstral-2512 | 1 | 8,959 | 15.3s | 1 Good |
| SQL | gpt-5-mini | 2 | 11,284 | 68.3s | — |

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

### Decomposition Strategy — The Key Pivot

Iteration 1's black box forced a fundamental rethink. Instead of one monolithic LLM call that goes from document → SQL, we decomposed into **3 transparent stages**, each producing a reviewable artifact:

```
 BEFORE (Itr 1)                          AFTER (Itr 2+)
 ─────────────                           ─────────────
 Document → [BLACK BOX] → SQL            Document → EXTRACT → PLAN → SQL
                                                      ↓         ↓        ↓
 Human can see output,                          "I found    "I'll    "Here's
 can't verify reasoning                          these"     do this"  the code"
```

**Why this works:**

1. **Each step = reviewable artifact** — no more opaque outputs
2. **Each step = different model** — expensive where quality matters (Plan), cheap where mechanical (Extract, SQL)
3. **Plan = human checkpoint** — separates "what did the AI understand?" from "what code will it generate?"
4. **Errors are localized** — bad SQL? Check the Plan. Bad Plan? Check the Extraction.

This decomposition enabled every subsequent optimization: prompt distillation, per-step feedback, model comparison, and the trust lifecycle.

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
                 │ gemini-3  │     │ gemini-3  │     │ gemini-3  │
                 │ flash     │     │ flash     │     │ flash     │
                 │ ~5s       │     │ ~16s      │     │ ~6s       │
                 │ 2.8K tok  │     │ 9K tok    │     │ 7.5K tok  │
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
  │  Sonnet 4.6 (plan step):  36s, 12,164 tok, ~$0.12/run     │
  │  gpt-5-mini (plan step): 124s, 13,663 tok, ~$0.01/run     │
  │  gemini-3-flash (plan):   16s,  8,998 tok, ~$0.003/run    │
  │  gemini-3.1-flash-lite:    7s,  8,568 tok, ~$0.001/run    │
  │                                                             │
  │  How: Run Sonnet once → extract 6 structural reasoning     │
  │  patterns (INSERT order, ID chaining, rule granularity,    │
  │  value derivation, natural keys, existence checks) →       │
  │  encode as PLANNING GUIDANCE in cheaper model's prompt     │
  │                                                             │
  │  Result: ~40–120x cost reduction, same output quality,     │
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

### Iteration 3 — Reconciliation + Guardrails *(where we are today)*

**The problem from Itr 2:** Decomposition made the AI's reasoning visible, but two critical gaps remained: (1) validating extracted rules across 20–30 rows was still hard, and (2) the pipeline was stateless — it didn't know what was already in the database. Upload the same company with a slightly different name ("ACMI Manufacturing Co" vs "Acme Manufacturing Corporation") and you get duplicate rows. Upload a policy with the same effective date as an existing one — no warning.

**The solution:** Two things. First, a **playground** sandbox for safe SQL execution. Second, a new **entity reconciliation** step: after extraction, the system queries existing DB records and uses the LLM to semantically match extracted entities against them. It catches typos, abbreviations, and name variations — then runs deterministic conflict checks for date overlaps and active-policy collisions. The pipeline becomes *database-aware*.

```
┌──────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│  Upload  │────▶│  EXTRACT  │────▶│ RECONCILE │────▶│   PLAN    │────▶│    SQL    │
│  Policy  │     │ + guardrails     │ (NEW)           │ + confidence    │ + validation
└──────────┘     └─────┬─────┘     └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                       │                 │                  │                  │
                 ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
                 │ 8-category│     │ LLM fuzzy  │     │ Confidence │     │ Playground│
                 │ rule      │     │ matching   │     │ deduction  │     │ vs Prod   │
                 │ exclusion │     │ vs existing│     │ rubric     │     │ isolation │
                 │           │     │ DB records │     │            │     │           │
                 │           │     │            │     │ Uses       │     │           │
                 │           │     │ + date     │     │ matched    │     │           │
                 │           │     │   overlap  │     │ IDs from   │     │           │
                 │           │     │   detection│     │ reconcile  │     │           │
                 └─────┬─────┘     └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
                       │                 │                  │                  │
                       ▼                 ▼                  ▼                  ▼
               ┌───────────────────────────────────────────────────────────────────┐
               │     Human still reviews 100% (Phase 1)                           │
               │     But system now collects:                                     │
               │       • Per-step ratings (G/P/B)                                │
               │       • Per-model token usage + latency                         │
               │       • Aggregated model stats via /stats                       │
               │       • Entity match confidence + conflict warnings             │
               │                                                                  │
               │     When enough data accumulates:                               │
               │         ┌──────────┴──────────┐                                  │
               │         │                     │                                  │
               │    ▼ > 90% Good           ▼ < 90%                                │
               │  ┌──────────┐       ┌──────────────┐                             │
               │  │  Future: │       │  Continue    │                             │
               │  │  Auto-   │       │  Human      │                             │
               │  │  approve │       │  Review     │                             │
               │  └──────────┘       └──────────────┘                             │
               └───────────────────────────────────────────────────────────────────┘
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
7. **Stateless pipelines corrupt shared databases.** Entity reconciliation (LLM fuzzy matching + deterministic conflict checks) prevents duplicate orgs/policies from accumulating silently.
