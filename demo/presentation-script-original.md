# APPRENTICE - Presentation Script (Original - March 7 Live Presentation)

> **Target: 7 minutes total** (you cover everything: problem, demo, iterations, closing)
> **Style: Storytelling - meet Adam the Apprentice**

---

## OPENING - Problem + Meet Adam (45 seconds)

"Oh boy, it's been a long session, so I'll keep this light. Let's do some storytelling.

Every organization has rules in policy documents. But between the document and the database, things get lost. A rule is misread, entered wrong, or the policy changes and the system doesn't. That gap costs money and creates risk.

So we built an apprentice to close that gap. I'm calling him Adam. He works at the Fair Play Initiative, and this is what he looks like."

**[Show the dashboard]**

---

## ACT 1: LIVE DEMO (45 seconds)

"Adam's been here three days. What you see on screen is the tooling we built to supervise him. We decide which models he uses, we see his past results, we rate his work."

**[Upload a sample policy PDF]**

"I've given Adam a policy PDF. He highlights keywords by category. Checks if anything already exists in our system. Writes a plan in plain English with confidence scores. Then generates the SQL.

Every step is available for us to rate: Good, Partial, or Bad. Let's look at how Adam got here."

---

## ACT 2: DAY ONE - The Black Box (75 seconds)

**[Show Iteration 1 diagram]**

"Day one. We gave Adam a document. He wrote something, but we couldn't validate it. Document in, SQL out. A black box.

We asked: what are you doing? He said: 'Extracting keywords, planning, writing SQL.' Great. Show us each step separately so we can rate them.

That's **decomposition**. One opaque task broken into three transparent stages. Because when the output triggers disciplinary action, you need to know exactly why.

But Adam's plans were confusing. GPT-5-mini produced plans that were hard to follow. So we swapped in Claude Sonnet 4.6, ran it multiple times. About 12 cents per run, but the plans were crystal clear.

We studied how Claude worked. Six reasoning patterns. Wrote those into Adam's system prompt. Now the cheap model follows Claude's playbook. Same quality, 40 to 120 times cheaper. That's **prompt distillation**."

**[TRANSITION]:** "After day one, Adam could show his work. But he had no memory of what was already in the system."

---

## ACT 3: DAY TWO - Discovery Day (75 seconds)

**[Show Iteration 2 diagram]**

"Day two was all discovery.

Adam can't read names clearly. 'Acme Manufacturing' versus 'ACMI Manufacturing Co'? Two separate organizations. Same policy twice? Duplicates everything. In production, that silently corrupts your database.

So we did reconciliation training. Showed him real data, gave examples: if names are close, they're probably the same. Now Adam checks the database first, matches existing records, flags conflicts.

Second: tools. Adam was locked to GPT-5-mini. We gave him model selectors and a sandbox to test queries safely. Kept swapping models, rating results. 3 to 5 minutes came down to 31 seconds. Gemini 3 Flash: a few cents for the complete pipeline.

We also moved observability in-house. If you're supervising someone, you need the metrics right where you're working, not in an external tool."

**[TRANSITION]:** "By day two, Adam was smart, fast, and cheap. Day three: scaling up."

---

## ACT 4: DAY THREE (30 seconds)

**[Show Iteration 3 diagram]**

"Day three. Adam re-reads his entire training manual before every task. Same schema, same guidance. Like re-reading the company handbook every morning.

So we enabled **prompt caching**. Adam remembers the parts that don't change. The more he works, the cheaper he gets."

---

## ACT 5: CLOSING (90 seconds)

"Adam's been here three days. He needs about another week before we reduce supervision.

But Adam isn't the only apprentice we can deploy. Picture another AI agent, let's call him Peter, assigned to procurement, extracting terms from vendor contracts. Another agent, Roger, in legal, reading compliance documents. Theresa in healthcare, looking at patient forms and referrals. Each one is a digital persona, an AI agent onboarded into a specific domain.

They don't have to start from scratch. Look at what we built while onboarding Adam.

Model selectors so supervisors assign the right tool for each task. A sandbox, not just for safety, but a full working environment where you can seed sample data, reset anytime, and run robust end-to-end tests before anything goes near production. A feedback system where humans rate every step, and those ratings accumulate into performance stats. A reconciliation layer so the AI checks what already exists. Observability built directly into the UI.

All of that is the application. None of it is specific to attendance policies.

When Peter starts in procurement, he doesn't need a new app. New prompts, new schema. The selectors, the sandbox, the feedback, the reconciliation, it's all there. Same for Roger. Same for Theresa. Every new apprentice gets a safe space to prove themselves first.

That's the **Apprentice framework**. It closes the gap between what the policy says and what the system does, so the rules an organization designed are actually the rules that run. In retail, manufacturing, hospitality, healthcare, wherever documents become decisions, that gap is the problem. We built the system that closes it.

Thank you."
