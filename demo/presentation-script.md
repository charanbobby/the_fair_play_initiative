# APPRENTICE - Presentation Script

> **Style: Storytelling - meet Adam the Apprentice**
> **Format: Recording - no time constraints, full detail**

---

## OPENING - Problem + Meet Adam

"This is my capstone project for Building Agentic AI Applications. Let me tell you a story.

Here's a problem every organization has. Someone in HR just got a 47-page attendance policy update. Their job is to read every page, figure out the rules, and type them into the system. If they misread a threshold, an employee gets written up who shouldn't have been. If the policy changes and nobody updates the system, the wrong rules run for months.

That gap between what the document says and what the system does exists everywhere. HR, procurement, legal, healthcare. Someone reads a document and types it into a database. It's skilled, tedious work, and it's the bottleneck of every organization.

So we built a framework to close that gap. We call it **Apprentice**. It's a supervised onboarding system for AI agents. You give it an agent, a domain, and a schema, and it provides the tooling to train, measure, and gradually trust that agent.

Adam is our first agent. He works at the Fair Play Initiative, a workforce attendance compliance system, and this is what he looks like."

**[Show the dashboard]**

---

## ACT 1: LIVE DEMO

"Adam's been here three days. What you see on screen is the tooling we built to supervise him. We decide which models he uses, we see his past results, we rate his work."

**[Upload a sample policy PDF]**

"I've given Adam a policy PDF. Watch what he does. He highlights keywords by category: organizations, regions, policy types, attendance rules. Checks if anything already exists in our database. Writes a plan in plain English with confidence scores. Then generates the SQL.

Every step is available for us to rate: Good, Partial, or Bad. That feedback is how we measure whether Adam is getting better or worse over time.

Let's look at how Adam got here."

---

## ACT 2: DAY ONE - The Black Box

**[Show Iteration 1 diagram]**

"Day one. We gave Adam a document. He wrote something, but we couldn't validate it. Document in, SQL out. A black box.

We asked: what are you doing in there? He said: 'I'm extracting keywords, making a plan, writing SQL.' Great. Show us each step separately so we can check your work.

That's **decomposition**. One opaque task broken into three transparent stages. Because when the output triggers someone's disciplinary action, you need to know exactly why.

But Adam's plans were confusing. He was running on GPT-5-mini and the output was hard to follow. So we swapped in Claude Sonnet 4.6 and ran the same task. The plans came back crystal clear.

We studied those plans, found six reasoning patterns Claude was using, and wrote them into Adam's prompt. Now the cheap model follows that same playbook. Same quality, 40 to 120 times cheaper. That's **prompt distillation**. Study the strong model, write down what it does, teach it to the cheap one.

We also tried something called RAG, Retrieval-Augmented Generation. The idea is: instead of giving Adam the whole document, you chop it into pieces, turn each piece into numbers that capture its meaning, that's called an embedding, and let Adam search for just the relevant parts. Like a librarian who finds pages by meaning, not by keyword.

So we showed Adam this machine. He fed the policy in, it made 26 chunks, and when he searched... it returned 20 of the 26. 97.3% of the document. Took twice as long, used 80% more tokens.

Adam's job is exhaustive extraction. He needs every rule, every threshold, every escalation level. He doesn't need a search engine, he needs the whole document. The machine was looking for needles, but Adam needs the whole haystack. So we sent it back."

**[TRANSITION]:** "After day one, Adam could show his work, and we knew which tools helped and which didn't. But he had no memory of what was already in the system."

---

## ACT 3: DAY TWO - Discovery Day

**[Show Iteration 2 diagram]**

"Day two was all about giving Adam awareness.

Adam can't read names consistently. 'Acme Manufacturing' versus 'ACMI Manufacturing Co'? To him, those are two separate organizations. Upload the same policy twice? He duplicates everything. In production, that silently corrupts your database.

So we trained him on reconciliation. Now Adam checks the database first, matches against existing records, and flags conflicts like overlapping dates or duplicate policies. The human reviews what he flagged before anything gets written.

Second: tools. Adam was locked to GPT-5-mini. We gave him model selectors, a different model for each step. And a sandbox to test queries safely. We kept swapping models, rating results. 3 to 5 minutes came down to 31 seconds. Gemini 3 Flash, a few cents for the whole pipeline.

We also moved observability in-house. Token counts, costs, latency, all visible in the UI where the supervisor works. If you're supervising someone, you need the metrics right where you're looking."

**[TRANSITION]:** "By day two, Adam was smart, fast, and cheap. Day three was about making sure he stays honest."

---

## ACT 4: DAY THREE - Hardening

**[Show Iteration 3 diagram]**

"Day three. Two problems.

First: Adam re-reads his entire training manual before every task. Same schema, same guidance, every time. Like re-reading the company handbook every morning. So we enabled **prompt caching**. The parts that don't change, Adam remembers between runs. The more he works, the cheaper he gets.

Second: we caught Adam making mistakes that looked like correct work.

He was misclassifying things. FMLA showed up as a 'region' in his extraction. FMLA isn't a place, it's a federal law. If that flows downstream, you get a region called 'FMLA' next to 'Ohio' in your database. Perfectly formatted. Completely wrong.

He was over-extracting. Turning glossary definitions and HR procedures into rules. A policy should give 20 to 25 rules. Adam was giving us 50.

And the worst one: when something was missing from the document, Adam made it up. No effective date? He'd invent one. A realistic date that enters your database as if it came from the source. That's hallucination at its most dangerous, because it looks correct.

So we hardened his prompts. Entity-type boundaries so laws stay in the law field and regions stay in the region field. Exclusion categories so definitions and procedures don't become rules. And absence handling: when data is missing, Adam says NOT FOUND instead of guessing.

That's **prompt hardening**. You don't just tell the AI what to do. You tell it what not to do, and what to do when there's nothing to do."

---

## ACT 5: CLOSING

"Adam's been here three days. He needs about another week before we reduce supervision.

But Adam isn't the only agent we can onboard. Picture Peter in procurement, extracting terms from vendor contracts. Roger in legal, reading compliance documents. Theresa in healthcare, reviewing patient forms. Each one onboarded into a specific domain.

They don't start from scratch. Look at what we built with Adam: model selectors, a sandbox for safe testing, a feedback system that tracks performance, a reconciliation layer, in-UI observability, and prompt hardening patterns that transfer to any domain.

None of that is specific to attendance policies. When Peter starts in procurement, he gets new prompts and a new schema. Everything else is already there.

That's the **Apprentice framework**. It closes the gap between what the policy says and what the system does. Wherever documents become decisions, that gap is the problem. We built the system that closes it.

Thank you."
