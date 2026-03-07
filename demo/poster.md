# SYSTEM DESIGN

## Business Constraints

- Errors in ingestion trigger wrongful disciplinary action
- AI output is inconsistent across runs
- Compliance teams will not adopt what they cannot inspect
- Must scale without expensive models

**Iteration 1: Decomposed Pipeline + Prompt Distillation**
- Agent reads a policy document and splits the work into 3 visible steps
- Step 1: Extract keywords by category
- Step 2: Write a plain-English ingestion plan
- Step 3: Generate SQL INSERT statements
- Human reviews and rates each step before the next one runs

**Iteration 2: Entity Reconciliation + Model Flexibility**
- Agent checks existing database records before writing anything new
- Flags conflicts: overlapping dates, duplicates, policy overwrites
- Supervisor picks which LLM model runs each step
- SQL executes in a sandbox, never against production
- Cost, latency, and feedback visible in the UI alongside results

**Iteration 3: Prompt Caching**
- Agent remembers static context (schema, guidance) between runs
- Each subsequent run is cheaper than the last

| Iter. | Cost/Latency Factors | Optimizations | Guardrails | Eval Metrics |
|-------|---------------------|---------------|------------|--------------|
| **1** | GPT-5-mini only; ~3-5 min per policy; Claude Sonnet 4.6 gold run ~$0.12 | 3-step decomposition (Extract, Plan, SQL); prompt distillation (6 patterns, 40-120x cheaper); meta-prompting: all prompts tested in playground against test data; RAG tested and rejected | Human G/P/B review at every step; Arize AX tracing | Per-step feedback ratings; Arize tracing spans |
| **2** | Gemini 3 Flash; 31s total (6x faster); $0.01-0.03/policy; 9 models, 71 runs | Per-step model selectors; entity reconciliation + fuzzy matching; in-UI observability replaces Arize AX | Sandbox SQL execution; conflict detection (date overlaps, duplicates, overwrites); human-in-the-loop approval | In-UI token count, cost, latency per step; feedback persisted to Supabase; model performance stats |
| **3** | 23.5K tokens from cache (5.5% of 427K); cost decreases with volume | Prompt caching on Plan + SQL steps | Same as Iter 2 | Cache hit/miss badges; cache token ratio per run |
