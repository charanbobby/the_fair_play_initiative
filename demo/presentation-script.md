# APPRENTICE - Presentation Script

> **Your part: ~6 minutes** (teammate covers the problem statement, then hands off to you)
> **Style: Storytelling - meet Adam the Apprentice**

---

## HANDOFF LINE

"Oh boy, it's been a long session today, so I'll keep this light. Let's do a little storytelling.

What you're about to see is an apprentice. I'm calling him Adam. Adam works at the Fair Play Initiative, and this is what Adam looks like."

**[Show the dashboard]**

---

## ACT 1: MEET ADAM - LIVE DEMO (60 seconds)

"Remember the problem my teammate described? Someone reads a document, figures out what it means, types it into a system. That's the job we hired Adam for. Except Adam is AI.

He's been here for three days. What you see on screen is the tooling we built to supervise him. We decide which models he uses, we see his past results, we rate his work."

**[Upload a sample policy PDF]**

"I've given Adam a policy PDF. Here's what he does:

First, he highlights keywords by category. Did he read the document correctly?

Next, he checks if anything already exists in our system. Matches instead of duplicating.

Third, he writes a plan in plain English. Table by table, with confidence scores. This is where we approve what he's about to do.

Finally, the SQL query. Every step is available for us to rate: Good, Partial, or Bad."

**[TRANSITION]:** "Let's look at Adam's evolution."

---

## ACT 2: DAY ONE - The Black Box (90 seconds)

**[Show Iteration 1 diagram]**

"Day one. We gave Adam a document. He wrote something, but we couldn't validate it. Document in, SQL out. A black box.

We asked him: what exactly are you doing? He said: 'I'm extracting keywords, planning, then writing SQL.' Great. Come back with each step separately so we can mark them Good, Partial, or Bad.

That's **decomposition**. One opaque task broken into three transparent stages: Extract, Plan, SQL. Because when the output triggers someone's disciplinary action, you need to know exactly why.

But Adam's plans were confusing. GPT-5-mini, a cheaper model, produced plans that were hard to follow.

So we swapped in Claude Sonnet 4.6, one of the most capable models, and ran it multiple times. About 12 cents per run, way more expensive, but the plans were crystal clear.

We studied how Claude worked. How it ordered inserts, chained IDs, handled rule detail. Six reasoning patterns. We wrote those into Adam's system prompt. Now the cheap model follows Claude's playbook. Same quality, 40 to 120 times cheaper. That's **prompt distillation**."

**[TRANSITION]:** "After day one, Adam could show his work. But he had no memory of what was already in the system."

---

## ACT 3: DAY TWO - Discovery Day (90 seconds)

**[Show Iteration 2 diagram]**

"Day two was all discovery.

First: Adam can't read names clearly. 'Acme Manufacturing' versus 'ACMI Manufacturing Co'? He creates two separate organizations. Same policy twice? Duplicates everything. For production, that silently corrupts your database.

So we did reconciliation training. Showed him the real data, gave him examples: if names are close, they're probably the same. Now Adam checks the database first, matches existing records, and flags conflicts.

Second: tools. Adam was locked to GPT-5-mini. We took him to a room full of tools, gave him model selectors and a sandbox to test queries safely. We kept swapping models and rating results. What took 3 to 5 minutes came down to 31 seconds. Gemini 3 Flash: a few cents for the complete pipeline.

We also moved observability in-house. On day one we used Arize AX, an external tool. But if you're supervising someone, you need the metrics right where you're working. So we built cost, latency, and feedback ratings directly into the UI."

**[TRANSITION]:** "By day two, Adam was smart, fast, and cheap. Day three: scaling up."

---

## ACT 4: DAY THREE - Adam Stops Repeating Himself (45 seconds)

**[Show Iteration 3 diagram]**

"Day three. We noticed Adam re-reads his entire training manual before every single task. Same schema, same guidance, same examples. Like an employee re-reading the company handbook every morning.

So we enabled **prompt caching**. Now Adam remembers the parts that don't change. First read is full price, every time after that is from memory. The more he works, the cheaper he gets. And that matters if we want him handling policies at volume."

---

## ACT 5: ADAM'S FUTURE - Closing (90 seconds)

"Adam's been here three days. He needs about another week before we start reducing supervision.

But Adam isn't the only apprentice. There's Peter, starting in procurement in a couple of weeks, extracting terms from vendor contracts and RFPs. Roger in legal, reading compliance documents and extracting requirements. Theresa in healthcare, looking at patient forms and referrals.

And here's the thing: they don't have to start from scratch. Look at what we've already built while onboarding Adam.

We built model selectors so supervisors can assign the right tool for each task. We built a sandbox where AI can execute queries without ever touching production data. We built a feedback system where humans rate every step, and those ratings accumulate into model performance stats. We built a reconciliation layer so the AI checks what already exists before writing anything new. We built observability directly into the UI so you never have to leave the app to supervise.

All of that is the application. And none of it is specific to attendance policies.

When Peter starts in procurement, the pipeline is already there. The model selectors, the sandbox, the feedback ratings, the reconciliation, the cost tracking. Peter just needs new prompts and a new schema. Same for Roger in legal. Same for Theresa in healthcare.

That's the **Apprentice framework**. It's not just Adam. It's the entire infrastructure for onboarding AI into any domain where someone reads a document and types data into a system. We built it once with Adam, and every apprentice after him inherits the tooling, the workflow, and the lessons learned.

Thank you."
