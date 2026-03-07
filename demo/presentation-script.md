# APPRENTICE - Presentation Script

> **Your part: ~7 minutes** (teammate covers the problem statement, then hands off to you)
> **Style: Storytelling - meet Adam the Apprentice**

---

## HANDOFF LINE

> *Your teammate finishes the problem statement. Set a light, conversational tone.*

"Oh boy, it's been a long session today, so I'll try to keep this light. Let's do a little bit of storytelling.

What you're about to see is an apprentice. And this apprentice, I'm calling him Adam. Adam works at the Fair Play Initiative, and this is what Adam looks like."

**[Show the dashboard]**

---

## ACT 1: MEET ADAM - LIVE DEMO (60-90 seconds)

> *Introduce Adam's capabilities by walking through a live run. Keep it conversational.*

"Remember the problem my teammate just described? Someone reads a document, figures out what it means, types it into a system. That's the job we hired Adam for. Except Adam is AI.

He's pretty new though. He's only been working here for three days. So what you're seeing on screen is all the tooling we built to supervise him. We decide which models he uses for each task. We can see what tools we assigned him in the past and what results he produced. The planning task is harder than extraction, so we might assign a more capable model for that step.

Let's watch him work."

**[Upload a sample policy PDF]**

"I've given Adam a policy PDF and asked him to update our system. Here's what he does:

First, he's highlighting all the keywords in the document, organized by category. This tells us: did Adam actually read the document correctly?

Next, he's clearly identifying if anything already exists in our system. If an organization is already there, he matches it instead of creating a duplicate.

Third, he's writing out a plan in plain English. What he intends to do, table by table, with confidence scores. This is the step where we, as his supervisors, can read and approve what he's about to do.

And finally, he writes the actual SQL query.

All of these steps are available for us to rate: Good, Partial, or Bad."

**[TRANSITION]:** "Now let's look at Adam's evolution. How he went from a messy first day to what you just saw."

---

## ACT 2: DAY ONE - The Black Box (90-120 seconds)

> *Adam's first day on the job. Eager but opaque. Also: his plans were confusing.*

**[Show Iteration 1 diagram]**

"Day one. We gave Adam a document and asked him to update the database. Adam wrote something, but it was really hard for us to validate what he was doing. It was one big action: document in, SQL out. A black box.

So we sat down with Adam and asked: what exactly are you doing?

He came back and said: 'Well, I'm looking at the document, I'm extracting and highlighting keywords, I'm doing a little bit of planning, and then I'm writing a SQL query.'

Great. So we told him: come back with the results of each step separately, so we can mark them as Good, Partial, or Bad.

That's the key decision of day one. This technique is called **decomposition**, breaking one opaque task into transparent stages. Adam was doing everything in one shot. Now we broke it into three stages: Extract, Plan, SQL. Each step produces something we can review. Because when the output triggers someone's disciplinary action, you need to know exactly why the system made that decision."

**[Show the three-step pipeline]**

"But there was another problem on day one. Adam's plans were... confusing. He was using GPT-5-mini, a smaller, cheaper model, and the plans it produced were hard to follow. Each run took 3 to 5 minutes.

So we did something interesting. We swapped GPT-5-mini with Claude Sonnet 4.6, one of the most expensive and capable models available, and ran it multiple times on the same planning task. Each run cost about 12 cents, way more than GPT-5-mini, but the plans it produced were crystal clear. Well-structured. Easy to verify.

Then we studied exactly how Claude worked. How it ordered its database inserts. How it chained IDs between tables. How it broke rules down to the right level of detail. Six reasoning patterns in total.

And here's the key part: we wrote those patterns into Adam's training manual. His system prompt. So now when Adam uses the cheaper model, he follows Claude's playbook. Same quality plans, but 40 times cheaper. With an even smaller model, 120 times cheaper. No fine-tuning, no training data, no GPU time. Just a few mentoring sessions, encoded as instructions. This technique is called **prompt distillation**, taking the reasoning of an expensive model and encoding it into the instructions for a cheaper one."

**[TRANSITION]:** "So after day one, Adam could show his work, and his plans made sense. But he still had no memory. He didn't know what was already in the system."

---

## ACT 3: DAY TWO - Discovery Day (90-120 seconds)

> *Two discoveries: Adam can't read names clearly, and there's a room full of tools.*

**[Show Iteration 2 diagram]**

"Day two. Adam comes back, and we start looking at his results more carefully. Actually, day two was a lot of discovery.

The first thing we discovered: Adam can't read names clearly. If words are misspelled or slightly different, he treats them as completely different things. Upload a policy for 'Acme Manufacturing,' then upload one for 'ACMI Manufacturing Co,' and Adam creates two separate organizations. Upload the same policy twice, and he duplicates everything.

For a demo, that's annoying. For production, that silently corrupts your database.

So we sat down with Adam and did something like reconciliation training. We took him to the real systems, showed him the actual data, and gave him a bunch of examples: if these names are close, they're probably the same entity. That's what you saw in the demo, the reconciliation step. Adam now checks the database before making his plan, matches against existing records, and flags conflicts like overlapping date ranges."

**[Point to model selectors and playground in the UI]**

"The second discovery was about tools. Originally, Adam was only allowed to use GPT-5-mini. We were worried that if we gave him more expensive tools, the costs would add up. We'd have to run hundreds of test cases.

So we took Adam to a room full of tools. We gave him a model selector for each step, so we could assign different models for different tasks. We also gave him a sandbox environment where he could write his queries and see the results without any risk to production data.

We kept uploading policies, swapping models, and rating the results: Good, Partial, Bad. And that's where the real discovery happened. What was taking 3 to 5 minutes, we brought down to 31 seconds. We discovered Gemini 3 Flash was really good. A few cents per policy for the complete end-to-end pipeline: extraction, reconciliation, planning, SQL generation, and execution. So we kept assigning that one.

We also moved observability in-house. On day one we were using Arize AX, an external tracing tool, which meant you had to leave the app to check how Adam was performing. If you're supervising someone, you need the metrics right where you're working. So we built token badges, cost per step, latency, and feedback ratings directly into the UI, all persisted to our analytics database."

**[TRANSITION]:** "By the end of day two, Adam was smart, fast, and cheap. Day three was about scaling that up."

---

## ACT 4: DAY THREE - Adam Stops Repeating Himself (60-90 seconds)

> *Continue the story. Caching framed as Adam getting smarter about repetition.*

**[Show Iteration 3 diagram]**

"Day three. Adam is fast, he's accurate, and he's cheap. But we noticed something: every time Adam processes a policy, he re-reads the same training manual from scratch. The database schema, the planning guidance, the examples we wrote for him. It's the same material every single time, and he's reading it like it's brand new.

Think of it like an employee who re-reads the company handbook before every single task. It works, but it's wasteful.

So we enabled **prompt caching**. Now Adam remembers the parts of his instructions that don't change between runs. The first time he reads the handbook, it's full price. Every time after that, it's served from memory.

The more policies Adam processes, the more efficient he gets. And that matters because if we want Adam to eventually handle routine work on his own, the cost per run needs to be low enough to process policies at volume."

---

## ACT 5: ADAM'S FUTURE - Closing (60-90 seconds)

> *Adam mentors other apprentices. Tie back to the Apprentice framework.*

"So Adam's been working here for three days. I think he needs about another week before he's ready to work more independently. At that point, we start reducing supervision. High-confidence steps auto-approve. We only review what Adam flags as uncertain.

But here's where the story gets interesting. Adam isn't the only apprentice out there.

There's Peter. Peter is about to start in the procurement division in a couple of weeks. He'll be onboarding vendors, extracting terms from contracts and RFPs, and updating the procurement system.

There's Roger, who'll be working in legal. Reading legal documents, extracting requirements, flagging compliance issues.

And there's Theresa, who's getting ready to take on healthcare. She'll be looking at patient forms, referrals, and coverage documents.

And you know what? They don't have to go through the same discovery that Adam did. Adam is going to meet all of them and say: here's what worked, and here's what didn't. The decomposition patterns, the distillation playbook, the reconciliation training, all of that transfers.

And that's the **Apprentice framework**. It's not just one AI assistant doing one job. It's a model for onboarding AI into any domain where someone reads a document and types data into a system. Each apprentice starts supervised, earns trust through measurement, and passes what it learned to the next one.

Thank you."
