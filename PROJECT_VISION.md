# Project Vision

## Beyond the Form: A Framework for Verifiable Agentic Workflows

---

## Core Thesis

Every enterprise runs on the same hidden workflow: someone reads a document, figures out what it means, and types the important parts into a system. HR reads a policy and enters attendance rules. Claims adjusters read medical records and enter coverage decisions. Procurement teams read contracts and enter vendor terms. It's skilled, tedious work — and it's the bottleneck of every organization.

AI can read those documents. But here's the problem: **AI doesn't give you the same answer twice.** Ask it to extract rules from a policy today and you get one result. Ask tomorrow, you might get something slightly different. That's fine for writing emails. It's not fine when the output triggers someone's disciplinary action, denies an insurance claim, or commits your company to a vendor contract.

**This project is about solving that problem.** We're building a control layer that takes unreliable AI output and makes it enterprise-reliable — not by hoping the AI gets it right, but by giving humans the right checkpoints to catch what it gets wrong, and then measuring the system into trustworthiness over time.

**The Fair Play Initiative** is where we prove this works — starting with workforce attendance compliance, where the stakes are real and the margin for error is zero.

---

## 1. The Big Shift: How Work Changes When AI Enters the Picture

Software used to be straightforward. You build it, you test it, you ship it. The same input always produces the same output. If something breaks, you find the bug and fix it.

AI flips that model on its head.

| | Traditional Software | AI-Powered Software |
|--|---------------------|---------------------|
| **How it works** | Same input = same output, every time | Same input can produce different results each time |
| **Where the effort goes** | 80–90% building: writing logic, fixing bugs | 80–90% evaluating: checking outputs, tuning quality |
| **When is it "done"?** | When the bugs are fixed, you ship it | Never — it's a continuous loop of monitoring and improving |
| **When things go wrong** | Bugs are predictable and reproducible | Failures are subtle, inconsistent, and can drift over time |
| **What the human does** | Operates the system: fills forms, clicks buttons | Supervises the system: reviews AI output, approves or rejects |

The challenge is clear: **businesses need guarantees** — precise compliance, exact calculations, auditable decisions. We're building the architecture that delivers those guarantees using technology that, by its nature, doesn't offer them.

---

## 2. The Solution: Show Your Work, Then Ask Permission

Most AI tools work like a black box — document goes in, result comes out, and you just have to trust it. We don't think that's good enough for enterprise use. Instead, we break the process into three visible steps, each producing something a human can actually read and judge.

### Step 1 — Extract: "Here's what I found in your document"

The AI reads a document the same way a person would — a dense PDF, a legal policy, a contract — and pulls out the key information: names, rules, thresholds, dates, relationships. But instead of a vague summary, it produces a **structured breakdown** mapped to your actual database fields.

Think of it as the AI filling out a checklist: "I found these organizations, these rules, these thresholds, these exceptions."

### Step 2 — Plan: "Here's what I'm going to do with it"

This is the step that makes everything else work. Before anything gets written to a database, the AI lays out its plan in plain language: *"I'm going to create this policy, link it to this organization and region, add these five rules with these point values, and flag this exemption."*

A compliance officer doesn't need to understand databases to read this. They can look at it and say: **"Yes, that matches the policy"** or **"No, you missed the part about excused absences."**

This is our **Verification Gate** — the moment where unreliable AI reasoning becomes a reviewable, approvable artifact.

### Step 3 — Execute: "Approved? Done."

Once a human signs off on the plan, the system carries it out. At this point, it's just following instructions — no AI judgment involved. The plan said what to do, the human agreed, and the system does it. Deterministic. Auditable. Done.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  Upload      │────▶│   Extract    │────▶│    Plan      │────▶│  Human   │
│  Document    │     │  "I found…"  │     │  "I'll do…"  │     │  Review  │
└──────────────┘     └──────────────┘     └──────────────┘     └────┬─────┘
                                                                    │
                                                         ┌─────────▼─────────┐
                                                         │  Approve / Reject │
                                                         └─────────┬─────────┘
                                                                   │ ✓ Approved
                                                         ┌─────────▼─────────┐
                                                         │     Execute       │
                                                         └─────────┬─────────┘
                                                                   │
                                                         ┌─────────▼─────────┐
                                                         │  Database Updated │
                                                         └───────────────────┘
```

**This pattern isn't specific to any one industry.** The three steps stay the same whether you're processing HR policies, insurance claims, vendor contracts, or regulatory filings. What changes is the document, the domain knowledge, and the person reviewing the plan.

---

## 3. Three Ideas That Drive Everything

### The real work is checking, not typing

In traditional software, the job is data entry — someone reads a document and types the information into forms. In this system, the AI does the reading and proposes what to type. The human's job shifts to **checking whether the AI got it right.**

That means the most important thing we build isn't the AI pipeline — it's the **evaluation system** that measures how often the AI's output matches reality:

- Did the extraction catch every rule in the document, or miss some?
- Does the plan reflect what the policy actually says?
- Every thumbs-up, thumbs-down, or "partially correct" rating builds a track record we can measure

### The interface should make you a better reviewer

If we're asking humans to supervise AI, the interface needs to make that job easy — not dump raw data and hope for the best:

- **Organized views** that group extracted information by category, so you can scan it quickly
- **Confidence indicators** that tell you where the AI is uncertain, so you know where to look closely
- **Sandbox mode** where you can test the system on sample documents without any risk
- **Model selection** so you can try different AI models for different steps and compare quality

### Trust is earned, not declared

You don't flip a switch and call the system "reliable." You measure your way there:

| Phase | What the human does | What the system learns |
|-------|--------------------|-----------------------|
| **Hands-on** | Reviews every single output, rates each step | Builds a baseline: "How often does the AI match the human?" |
| **Building trust** | Reviews only the flagged items, trusts the high-confidence ones | Tracks agreement rates, surfaces the disagreements |
| **Autonomous** | Handles exceptions only | The AI has proven itself over enough reviews that routine work flows through automatically |

The feedback from Phase 1 is what makes Phase 3 possible. You can't skip to the end.

---

## 4. Where This Is Heading

The end goal isn't a better data-entry form. It's **no data-entry form at all.**

- **Right now:** You upload a document, review the extraction, check the plan, rate each step, and approve. The interface is your workspace.
- **Next:** You open a dashboard that shows what the system processed overnight — confidence scores, flagged anomalies, a summary of decisions made. The interface is your audit panel.
- **Eventually:** The only things that reach a human are genuine edge cases — unusual documents, ambiguous language, cross-jurisdictional conflicts. Everything routine is handled.

The human isn't removed from the process. They're promoted — from **data entry clerk** to **quality supervisor**.

---

## 5. This Pattern Works Across Industries

Anywhere someone reads a document and enters data into a system, this pipeline applies:

| Industry | The Document | What Gets Extracted | The Plan | The Result |
|----------|-------------|--------------------|-----------|----|
| **Workforce Compliance** *(FPI)* | HR attendance policies | Rules, point values, thresholds, exemptions | "Create policy, add 5 rules, link to region" | Policy and rules in compliance database |
| **Insurance** | Claims, medical records | Diagnoses, procedures, coverage terms | "Approve claim, apply deductible, flag for review" | Adjudication decision and payout |
| **Procurement** | Vendor contracts, RFPs | Terms, SLAs, pricing, penalties | "Onboard vendor, set payment terms, flag SLA risk" | Contract records and payment schedule |
| **Regulatory** | Legal filings, compliance docs | Requirements, deadlines, obligations | "Map to reporting schedule, flag gaps" | Filing submissions and audit trail |
| **Healthcare** | Patient forms, referrals | Demographics, conditions, medications | "Assign provider, schedule intake, flag allergies" | EHR records and care plan |

Same bones, different skin. Extract → Plan → Verify → Execute.

---

## 6. The Fair Play Initiative: Where We're Proving It

We chose workforce attendance compliance as our first domain because it's a perfect test case: the documents are complex (multi-page HR policies with nested rules and exceptions), the consequences are real (point accumulations trigger disciplinary action), and there's zero tolerance for error.

### What's Working Today (v0.7.x)

**The AI Pipeline:**

- Upload an HR policy (PDF, DOCX, or paste text directly)
- Step 1 extracts keywords mapped to the database schema — policies, rules, organizations, regions, employees
- Step 2 generates a structured ingestion plan with table-by-table steps, individual rule rows, dependency chains, and confidence scores
- The human reviews, rates each step (Good / Partial / Bad), and approves or rejects

**The Operational Platform:**

- Multi-tenant setup: Regions (with labor law context) → Organizations → Policies → Rules → Employees
- Points-based discipline with configurable thresholds and rolling windows
- CSV attendance upload with automatic scoring against active rules
- Full audit trail — every point change, whether from a violation or a manual override, is recorded
- Dashboard with KPIs, 6-month trends, employee risk grid, and alerts
- Playground mode for safe testing with sample policies and seed data

**The Measurement Infrastructure:**

- Human feedback on every step → building the dataset that proves (or disproves) reliability
- Token usage, response time, and cost tracking per model per step
- Swap AI models per pipeline stage to compare quality and cost
- Optional deep tracing via Arize for full observability

### Technical Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI + SQLAlchemy 2.0 + Pydantic v2 | Type-safe, async, validated |
| AI Pipeline | LangChain + LangGraph | Multi-step stateful processing |
| LLM Access | OpenRouter (model-agnostic) | Switch models without changing code |
| Database | SQLite (dev) / PostgreSQL on Supabase (prod) | 11 tables, full referential integrity |
| Frontend | Vanilla JS + Tailwind + Chart.js | No build step, fast to iterate |
| Deployment | Docker → Hugging Face Spaces | One container, production-ready |
| Observability | Usage logs + human feedback + Arize OTLP | Track cost, quality, and trust over time |

---

*Beyond the Form — making enterprise document processing verifiable, auditable, and progressively autonomous.*
