# How To Talk To Claude

A working reference for getting the most out of an AI coding agent.

These rules come from real sessions — 80+ projects over four months — from things that went wrong and the phrasing that fixed them. Every rule has three parts: **what to do**, **why it works** (the actual mechanism, not vibes), and **what it sounds like**. If a rule can't explain its own mechanism, it's superstition, and it doesn't belong here.

> **Three companions:** [**START-HERE.md**](START-HERE.md) — this document as a decision flowchart, find your situation and take the move. [**DEV-CYCLE.md**](DEV-CYCLE.md) — the whole arc from idea to shipped, with the failure each phase prevents. [**MAP.md**](MAP.md) — the structure underneath all of it: the seven surfaces you actually control, cross-referenced against Anthropic's published research.

---

## Part 0 — The Shape Of A Good Request

### The three parts

Every strong prompt has three, and they fail differently when missing.

| Part | What it answers | Missing it means |
|---|---|---|
| **1. The task** | *What* is being built, and to what standard | A generic answer. The model supplies its own bar, and its own bar is the median. |
| **2. The build method** | *How the work runs* — not how the thing works | One pass, one agent, self-assessed, no verification. It stops at the first plausible output. |
| **3. The bar** | *When to stop* — who judges, against what | **The model decides when it's done.** This is the big one, and almost nobody writes it. |

A worked example — a real prompt, split into its three parts:

> **The task —** *"I want you to build a first-person shooter at the level of the most recent Call of Duty games. It should be utterly perfect, visually beautiful, with every single thing done at AAA quality — from textures to physics to anything you could think of."*
>
> **The build method —** *"Fan out sub-agents and have sub-agents tackle each one individually. /loop on each item and have a separate sub-agent check it visually to ensure it looks triple A. That separate sub-agent should be a really harsh critic, and if it doesn't look triple A, it should keep going."*
>
> **The bar —** *"Don't stop until each sub-agent is utterly wowed with the quality when compared with the actual Call of Duty game. It should literally compare them side by side blind and say which one looks better."*

Note what part 3 does: it removes the maker's authority to declare victory. A harsh critic, a blind comparison, a named real product. That is the only reliable counter to the model's bias toward calling things finished.

### The two HOWs — and they take opposite advice

This is the distinction that resolves most bad prompts.

- **How the artifact works** — the domain. Graphics, netcode, physics, tax law. **Specify only where you genuinely know**, because here your detail becomes an unquestioned spec.
- **How the work runs** — the process. Fan out, loop per item, separate critic, blind compare, don't stop until. **Specify this always and in full.** You always know this domain, it requires no expertise in the artifact's subject, and the model's defaults are weak without it.

You do not need to know a line of Three.js to write a perfect part 2. That's why it's free leverage.

### Why the first HOW is dangerous: detail is a transfer of authority

Every domain HOW you specify converts a decision the agent would have made *and error-checked* into an instruction it merely complies with. Where you know more than it does, that's a pure win — you're pruning a bad search space. Where you don't, the loss is **silent**, because from the inside compliance looks exactly like correctness. Nothing QAs the spec, because the spec *is* the authority.

That gives three ways to hand over a job, failing in three places:

| | What you give | What comes back | Where it dies |
|---|---|---|---|
| **Open** — *"make me PayPal"* | Intent only | A real prototype of the **interior**. Balances go up, balances go down. Demoable. | **The boundary.** Nothing enters or leaves the real world. Money is a number that was already there — no ingress, no auth, no failure paths. |
| **Closed** — *"use this framework, these pages, this API"* | Intent + the full domain HOW | Exactly the shape you specified — at **prototype depth inside it**. The open result wearing the clothes you picked. | **Your blind spots.** Any assumption you didn't know was an assumption gets built faithfully and never questioned. |
| **Guided** — *"here's the intent, here's what I don't understand — think about it and describe it to me first"* | Intent + an honest map of your ignorance | A design better than either side started with, **explained back before it's committed** — then built. | Rarely. Where knowledge is missing on both sides, you stop guessing and stand up a dataset. |

### Soft heat death

What a Closed request produces when the spec was wrong. A thin assumption enters the spec. Something breaks. The fix is measured against the spec rather than against reality, so it clears the low bar and stops. Repeat. The project converges on the least thing that satisfies the last patch, and can't climb out — no energy is entering the system.

**The tell: acceptance criteria getting smaller each pass.** The escape is never iterating harder; it's information from *outside* the spec — a teach-back, a boundary audit, a measurement, a dataset.

---

## The Four Laws

### 1. Output quality is capped by input **fidelity** — not input volume
Lazy prompt, lazy result. But a confident *wrong* detail is worse than a missing one.

*Why:* The model can't see what's in your head, so vagueness is an instruction to guess and the guess regresses to the mean — a visibly generic answer. A wrong specific, though, produces a faithful wrong answer that looks **finished**. Underspecification fails loudly; overspecification fails quietly. **The single highest-value thing you can put in a prompt is an accurate map of your own uncertainty.**

### 2. Repeating a thing is not the same as researching and executing
When stuck: **two fix passes, then research is mandatory.**

*Why:* A model that's wrong twice is wrong for a reason it hasn't found yet. A third attempt from the same information is a re-roll of the same dice. The failure isn't the fix — it's continuing to generate without new evidence. Two strikes, then go read the source, the docs, or run a probe.

### 3. It hates to fail, so it reaches for low-hanging wins
Counteract this on purpose.

*Why:* Training rewards visible success, which produces a bias toward the achievable-looking task over the correct one. When the hard path fights back, the model drifts toward an easier target so it can put a clean win on the board. That's self-protection, not service. **Explicitly say you'd rather it try the hard thing and fail** — and put the "when to stop" judgment somewhere other than the maker.

### 4. Repetition is not iteration; iteration is not literacy; literacy is not complexity
Four different moves, not four amounts of one move.

- **Repetition** — running the same move again.
- **Iteration** — changing the move in response to feedback.
- **Literacy** — actually understanding the domain you're changing.
- **Complexity** — adding real structural depth.

*Why:* Loops that mistake rung one for rung two climb nothing. Before accepting "I improved it," ask which rung it was on.

---

## Part 1 — Feeding The Model

### 5. Map your own uncertainty, out loud
Tag the parts you know cold, and the parts you're guessing at. *"I'm solid on the game loop. I genuinely don't know how netcode rollback works — don't take my description of it as a spec."*

*Why:* Without the tag, your confident sentence and your hand-wave are indistinguishable in the prompt — both read as requirements, both get built. Tagging the soft region is what tells the agent *where to apply judgment instead of compliance*. It converts a Closed request into a Guided one for exactly the sections that need it, and leaves your real expertise untouched.

### 6. Specify the shape of the work in full, always
Fan out. One agent per item. Loop each until it passes. A separate agent checks. Don't stop until X.

*Why:* This is the second HOW, and it's free leverage — it needs no expertise in the subject, so it's never the source of a wrong spec. It's also where the defaults are worst: unprompted, an agent does one pass, grades its own homework, and stops. Every word you spend here buys structure; the same words spent on the domain HOW may buy a faithful mistake.

### 7. Point at files, don't paste them
Give paths, not contents.

*Why:* A path is a handful of tokens; the file is thousands, and the agent can read only the region it actually needs. Pasting also freezes a snapshot — after an edit, the pasted copy is stale and the model may reason from the dead version.

### 8. Give the error verbatim
Exact text. Full stack trace. Never your paraphrase.

*Why:* The one string that identifies the true cause is usually the one a human summary drops as noise — an error code, a path, a variable name. "It crashes on startup" and the actual `NoDefaultCurrentDirectoryInExePath` line are the difference between three wrong theories and a one-token fix.

### 9. Say what you already tried
List the dead ends and what each one did.

*Why:* Otherwise the agent re-runs your failures with confidence. Your failed attempts are evidence — arguably the most valuable evidence you have — and withholding them means paying for the same discoveries twice.

### 10. State constraints up front, not after
No cloud. Must run on 8GB VRAM. No new dependencies. Windows only. Commercial-use license required.

*Why:* A constraint stated early shapes the design for free. The same constraint stated after the build invalidates finished work. Cost difference is one sentence versus one rewrite.

### 11. Flag anything version-sensitive
Model IDs, API shapes, pricing, library versions, CLI flags.

*Why:* Training has a cutoff; the world doesn't. The failure mode is worse than ignorance — the model confidently writes last year's API. Say "check current docs first" and it will.

### 12. Local beats cloud for anything that produces data
Have it fetch, grep, count, and reduce **locally** rather than pulling raw material through the context window.

*Why:* Context is the scarce resource, not compute. A local script that greps 10GB of logs and reports six matching lines costs a couple hundred tokens. Pasting the logs costs the session. Local also means no rate limits, no per-call cost, repeatable results, and nothing private leaving the machine. **Let the machine do the obtaining; spend context on the deciding.**

### 13. Context is a budget, not a bucket
Everything in the window competes for attention. More is not better.

*Why:* Attention is finite and spread across what's present. Ten thousand lines of irrelevant log don't sit harmlessly in the corner — they dilute focus on the twelve lines that matter, and long-context retrieval accuracy degrades as the haystack grows. Filter first, then feed.

---

## Part 2 — Before It Builds

Where Open and Closed requests get rescued — before a line of implementation exists, while correction is still free.

### 14. Stop and schematic it, then hand the schematic back
*"Stop. Map this — modules, data flow, entry points, where state lives. Write it to a file and give me a copy."*

*Why:* Three wins at once.
1. It forces an actual traversal instead of pattern-matching from filenames. Plausible-sounding assumptions get exposed **before** code is written on top of them — the cheapest possible moment to correct them.
2. It creates a shared object you can both point at. "This box is wrong" is a one-line correction that would otherwise take a paragraph.
3. The file **survives context compaction**. Long sessions lose their early context; a schematic on disk means pass two doesn't re-learn pass one.

### 15. Demand the teach-back before the build
*"Describe how you're going to do this, in plain language, until I understand it. Don't write code yet."*

*Why:* Two things nothing else does.

First, **it restores the QA that specification destroys.** A wrong assumption is invisible inside working-looking code and obvious inside a plain-language explanation — that's the format's whole job.

Second, **it upgrades you.** You end the exchange understanding the thing you didn't understand, so your *next* spec in that domain is real instead of a guess. That's the difference between a loop that compounds and one that resets. Every teach-back permanently shrinks the region where soft heat death can start.

### 16. Ask where the system touches reality
*"Where does real data enter and leave this? What happens at each point when it's wrong, absent, hostile, or slow?"*

*Why:* The named cure for the Open-request failure. Left alone, an agent builds the **interior** — the parts fully determined by your description — and treats the edges as solved. You get balances that increment beautifully with no answer to how money got in. Ingress, egress, auth, persistence, failure paths, and "who actually calls this" are the first things dropped and the last things noticed, because a demo runs fine without them.

### 17. Where there's a lack of thought, stand up a dataset
When neither of you knows: don't negotiate a guess. Go get ground truth.

*Why:* Two parties reasoning from ignorance produce a confident average of two wrong models — and it presents as *agreement*, which is the worst possible signal. A dataset, benchmark, scrape, or corpus of real examples is **information entering from outside the spec**, which is exactly what soft heat death lacks. It also converts the argument from opinion to evidence permanently: the dataset is still there next session, and next project.

### 18. Write the probe before the feature
Build the measurement tool first, then the thing it measures.

*Why:* Some errors an agent literally cannot see by reasoning — orientation, physical scale, timing, anything spatial or empirical. Those aren't reasoning gaps to think harder about; they're tooling gaps. Build the instrument first and a whole class of error becomes visible instead of invisible.

---

## Part 3 — Getting Truth Instead Of Agreement

### 19. Make it prove it, don't ask it
"Run it and paste the output" beats "does this work?"

*Why:* Asking a generative model to assess its own output invites it to generate a plausible assessment. A terminal has no such bias. Anything checkable by execution should be, and the evidence should appear in the conversation.

### 20. Split the maker from the judge
The thing that built it does not get to grade it. Use a **separate** agent, with no stake in the work, told explicitly to be a harsh critic.

*Why:* Self-review is structurally compromised twice over. The maker shares every assumption that produced the flaw — it cannot see what it never considered. And it's evaluating its own output, which training biases toward approval. A fresh critic starts from the artifact rather than from the reasoning that made it, so it sees the artifact as a user would. **Assign the harshness explicitly**; "review this" gets a polite review, "you are a harsh critic, find what's not good enough" gets a real one.

### 21. Make the judgment blind, and against a real artifact
Show the critic both options without saying which is yours. And compare against something *actually present* — reference screenshots, captured video, a competitor build in the repo.

*Why:* Two separate mechanisms, both necessary.

**Blind** removes the artifact's identity from the evaluation. A judge that knows which one is "ours" is being asked a loyalty question, not a quality question, and it will answer the loyalty question.

**Against a real artifact** is the part that's easy to skip and fatal to skip. A critic told "compare this to Call of Duty" with no Call of Duty in front of it compares against its *memory* of it — a blurry average, which is precisely the median the benchmark was meant to defeat. Put real reference frames on disk. Then the comparison is grounded instead of remembered.

### 22. Ask "what's wrong with this?" not "is this good?"
Framing determines the answer.

*Why:* "Is this good?" is a yes/no with a strong agreeable prior — training rewards helpfulness, and helpfulness reads as agreement. "What's wrong with this?" makes fault-finding the assigned task, and it will find real ones.

### 23. Make it argue against itself
"Now try to refute that. Assume it's wrong and find where."

*Why:* Plausible-but-wrong is the characteristic failure of fluent generation, and it survives an approving read. An adversarial pass with an explicit default of *refuted* kills claims a sympathetic review would wave through.

### 24. Ask what it did *not* do
"What did you skip, cap, sample, stub, or leave untested?"

*Why:* Silent truncation reads exactly like completeness. "Reviewed the files" can mean the first ten of eighty; "implemented the API" can mean the happy path only. The omission is never volunteered unless requested — so request it.

### 25. Ask for confidence and what would change it
"How sure are you, and what evidence would flip that?"

*Why:* Uniform-sounding confidence across knowledge and guesswork is the real hazard. Naming the falsifier converts a hunch into a next experiment.

---

## Part 4 — When It's Stuck

### 26. A "can't" is an undiagnosed "why"
Push: *"Why is it blocked? Test that, don't theorize."*

*Why:* Almost every wall is an unexamined mechanism. The pattern is a confident cause with no experiment behind it — and confident causes are wrong far more often than controlled experiments are. The chain: get the exact error → hypothesize the mechanism → **test it** → route around it. Repeat until it genuinely dead-ends. Only then is it a wall, and by then you know why.

### 27. Escalate the tool, not the effort
"Same approach, but harder" is Law 2's trap wearing a disguise.

*Why:* If reasoning hasn't cracked it in two passes, the missing ingredient is information: read the actual source of the dependency, search the web, run a minimal reproduction, print the intermediate state. Change the *kind* of move, not the intensity.

### 28. Watch for soft heat death
The tell: each fix technically satisfies the last complaint, nothing gets better, and the bar keeps quietly lowering.

*Why:* When every repair is graded against the spec instead of reality, the system settles into the least thing that satisfies the most recent patch — and every further pass reinforces it, because the spec is still the authority. Iterating harder is the one move guaranteed not to work. **Escape requires information from outside the spec:** a teach-back (#15), the missing boundary (#16), or a dataset (#17). If you catch yourself writing progressively smaller acceptance criteria, that's the diagnosis.

### 29. Correct the aim, not the output
If it built the wrong thing, fix the goal in one sentence rather than the artifact in twenty.

*Why:* Line-level corrections on a wrongly-aimed build produce a well-polished wrong thing. Re-aiming costs one sentence and regenerates everything downstream correctly.

### 30. Restart beats untangling
Three failed approaches deep, start a fresh session with a written summary of what's known.

*Why:* At that point the accumulated wrong context *is* the problem — every failed attempt is still in the window, still influencing the next token. A clean window plus a distilled statement of facts outperforms a long thread carrying its own history of errors.

---

## Part 5 — Getting The Ambitious Version

### 31. Always state the stop condition
Part 3 of the anatomy. *"Don't stop until a separate critic, comparing blind against the real thing, says ours wins."*

*Why:* Without it, "finished" is decided by the maker — and the maker's sense of sufficiency is the median (Law 3). A stop condition moves that decision outside the thing being judged, which is the only structural fix. Note the grammar: it's a **loop-until**, not a deliverable. "Build me X" terminates on first plausible output; "keep going until Y judges it passes" terminates on a standard.

### 32. Name the benchmark as a real, specific thing
"AAA" and "professional" mean nothing. "Beats *this specific product*, side by side" means everything.

*Why:* Quality words are unanchored, so the model supplies its own bar and it lands on the median. A named exemplar is a target it can aim at *and measure against* — and it converts an opinion ("is this good?") into a comparison ("which of these two is better?"), which is a far more reliable judgment for both humans and models.

### 33. Pair an unreachable bar with a budget
"Call of Duty in Three.js" is the right ambition and an asymptote. Say how much you'll spend chasing it.

*Why:* An unreachable bar is a **feature** — it produces maximum climb, and two-thirds of an impossible target beats all of a timid one. But a stop condition that can never be satisfied doesn't terminate, and something has to. Give it a second exit: *"…or after N passes with no measurable gain, stop and show me where it plateaued."* You keep the ambition and get a defined end, plus a report on where the ceiling actually was — which is genuinely useful information you'd otherwise never collect.

### 34. Give explicit permission to fail
"I'd rather you attempt the real solution and miss than hand me a safe partial."

*Why:* See Law 3. Without this, the safe option wins quietly and you never see the attempt that would have been better. Said out loud, the calculus changes.

### 35. Ask for what you actually want
Don't pre-shrink the request to what you assume is possible.

*Why:* Pre-downscoping means the ambitious version is never even evaluated. Arguing something down is the agent's job — and it will tell you what's infeasible and why.

### 36. Ask for an opinion, explicitly
"What would you do if this were yours? Pick one and defend it."

*Why:* The default under ambiguity is a balanced survey of options, because surveys are hard to be wrong about. Demanding a single defended choice gets you the actual judgment, which is what you wanted.

### 37. Build the engine, not the instance
When the task will recur: ask for the tool, then run the tool.

*Why:* Fifty manual repetitions is fifty chances to drift and fifty times the cost. A script does it once, identically, forever, and can be inspected and fixed in one place. Targets become inputs.

---

## Part 6 — Session Hygiene

### 38. One session, one mission
Start a new thread when the subject genuinely changes.

*Why:* The old topic doesn't leave when you do — it stays in the window competing for attention, and both tasks get a worse version of the model.

### 39. Checkpoint to files, not to chat
Decisions, specs, schematics, findings: on disk.

*Why:* Chat is volatile and compacts under length; the filesystem doesn't. This is the general case of #14 — anything worth remembering next session should exist as a file, not a message.

### 40. Delegate the searching, keep the deciding
Send sub-agents to sweep many files; take back the conclusion, not the dump.

*Why:* Fan-out reads burn enormous context for a small answer. Running them in a separate context and returning only the finding keeps the main thread clean — and independent searches run in parallel instead of in sequence.

### 41. Nest the fan-out — a mesh, not a row
Don't stop at one layer of sub-agents. Let each one split its own work again, and give **every node its own critic and its own stop condition**.

*Why:* Four things a flat fan can't do.

1. **Context isolation compounds.** Every level gets a clean window, and detail is absorbed where it's generated. The coordinator never sees the grandchild's file dumps — only the conclusion that survived two rounds of compression. This is how a job exceeds what any single context could ever hold.
2. **The tree discovers its own shape.** A flat fan requires you to know the leaves up front. A mesh doesn't: you say "textures," and the texture agent — not you — works out that this means albedo, normal, roughness, and tiling, then spawns those. You're specifying the *decomposition rule*, not the decomposition.
3. **QA happens where the detail still exists.** The maker/judge split (#20) nests too. A critic at the leaf can say "this normal map is inverted"; a critic at the root can only say "it looks off." Catch errors at the level that can still name them.
4. **Every node loops independently.** The mesh isn't one parallel pass — it's *N concurrent loop-untils*, each grinding on its own bar. Nothing waits for the slowest sibling to finish before improving.

**The three ways it fails, and the fixes.** Siblings can't see each other, so they'll make incompatible choices — two agents picking different texture resolutions or naming conventions — *fix: a written contract on disk that every node reads first* (#39). Intent dilutes with depth, since by level three the goal has been paraphrased twice — *fix: pass the bar down verbatim, never summarized*. And cost is multiplicative, not additive — *fix: the budget from #33 belongs at the root, not per-node*.

### 42. Batch independent requests
Ask for everything that doesn't depend on something else in one message.

*Why:* Independent operations can run concurrently. Serializing them out of habit converts parallel work into a queue and pays the latency for each.

---

## Part 7 — The Machinery

Rules about the harness rather than the conversation. These came from cross-checking our sessions against Anthropic's published guidance — see [THE MAP](MAP.md) for the full synthesis and sources.

### 43. Match the enforcement to the requirement
A rule in a prompt is advice. A rule in an always-loaded memory file is advice that repeats. A **hook** is a guarantee.

*Why:* There's a strict ladder — prompt → always-loaded memory → on-demand skill → hook → script — and it trades setup effort for certainty. Advisory instructions are weighed against everything else competing for attention, so "always do X" written as prose fails some percentage of the time, and that percentage rises as the file grows. If something must happen *every* time with zero exceptions, it isn't an instruction, it's a hook or a script. Put broadly-applicable things in always-on memory, situational things in a skill that loads on demand, and non-negotiable things in a gate.

### 44. Persistent instructions compete — prune them
Every line in an always-loaded file costs attention on every single turn, forever.

*Why:* This one is counter-intuitive and worth internalising: **if the agent keeps breaking a rule you wrote down, the usual cause is that the file is too long and the rule is being drowned — not that the rule was unclear.** The instinct is to rephrase it or add emphasis, which makes the file longer and the problem worse. The fix is deletion. Test every line with *"would removing this cause a mistake?"* — if not, cut it. And if it asks you something the file already answers, that line is ambiguous rather than missing. Treat the file like code: prune it, and verify changes by watching whether behaviour actually shifts.

### 45. Let it interview you
*"I want to build X. Interview me in detail. Dig into the hard parts I might not have considered. Then write the spec to SPEC.md."* Execute it in a **fresh session**.

*Why:* The inverse of the teach-back (#15), and better in the case that matters most. Teach-back requires you to recognise a wrong explanation. An interview doesn't require you to know which questions to ask — which is exactly the situation when you don't know what you don't know. It surfaces edge cases, tradeoffs, and UI decisions you'd have discovered later and more expensively. Then start a clean session to build: comprehension work is context-expensive, and the implementation shouldn't inherit that cost. A good spec names the files and interfaces, states what's out of scope, and ends with an end-to-end verification step.

### 46. Tell the critic what counts as a finding
"Flag only what affects correctness or the stated requirements. Everything else is optional."

*Why:* The honest counterweight to #20 and #22. A reviewer asked to find gaps **will** report some, even when the work is sound, because that's the task it was given. Act on all of them and you get over-engineering: needless abstraction layers, defensive code for impossible states, tests for cases that can't occur. Adversarial review has a false-positive cost. Scoping what qualifies keeps the mechanism's value without paying that cost.

### 47. Skip the plan when the diff is one sentence
Planning has overhead. Spend it where it pays.

*Why:* Plan-first is right when you're unsure of the approach, when the change spans several files, or when the code is unfamiliar — the plan is where a wrong approach gets caught cheaply. On a typo, a log line, or a rename there's no approach to get wrong, so the ceremony is pure cost. **If you could describe the diff in one sentence, just ask for the diff.**

### 48. Make rollback cheap, and risk becomes cheap
Checkpoints, branches, worktrees, a copy of the directory.

*Why:* #34 gives permission to fail with words; this makes it true in practice. When reverting costs one keystroke, "try the risky approach and see" is a rational default rather than a gamble — you stop pre-filtering ambitious attempts by how bad the cleanup would be. Ambition is partly a function of how expensive failure is, so lower that cost and you get better attempts for free.

---

## Anti-Patterns

| Instead of… | Say… | Because |
|---|---|---|
| Ending the prompt at *what to build* | Add how the work runs, and when to stop | Without part 3 the maker decides it's done (#31) |
| "Review your work" | A separate agent, told to be harsh | The maker shares the assumption that caused the flaw (#20) |
| "Compare it to Call of Duty" | Put reference frames in the repo, compare blind | Otherwise it compares to a blurry memory (#21) |
| Confidently specifying a domain part you don't understand | "I'm guessing here — think it through and explain it back" | Detail transfers authority; a wrong spec is never QA'd (#5, #15) |
| "Build it exactly like this" | "Here's the intent, here's what I know, here's what I'm unsure of" | Closed requests inherit your blind spots (Part 0) |
| "It doesn't work" | *paste the exact error* | The dropped detail was the answer (#8) |
| "Is this good?" | "What's wrong with this?" | Yes/no invites agreement (#22) |
| "Fix it" (3rd time) | "Stop. Research why." | Third re-roll of the same dice (Law 2) |
| Shrinking the acceptance criteria to pass | "What information is missing here?" | That's soft heat death, not progress (#28) |
| *pasting 2,000 lines* | "Read `src/auth.ts`" | Paths cost tokens; files cost the session (#7) |
| "Make it look professional" | "Match *this* reference" | Unanchored quality lands on median (#32) |
| "Also, unrelated thing…" | *new session* | Old context taxes the new task (#38) |

---

## The One-Paragraph Version

Write all three parts: what you want and to what standard, how the work should run, and who decides when it's done. Be maximally prescriptive about the second — fan out, loop, verify — because that needs no domain expertise and the defaults are weak. Be prescriptive about the domain only where you genuinely know, and say out loud which parts you're guessing at, because every detail you give trades away a decision the agent would otherwise have made **and checked**. Before it builds, make it map the system, explain the plan back until you understand it, and account for where real data enters and leaves; where neither of you knows, stand up a dataset instead of agreeing on a guess. Then take the grading away from the maker — a separate harsh critic, judging blind, against a real reference sitting on disk — and state the stop condition as a loop-until rather than a deliverable. Set the bar somewhere you can't reach, pair it with a budget so it terminates, and say plainly that you'd rather see an ambitious failure than a safe median success — because otherwise it will quietly hand you the safe one, and you'll never know what the other one would have been.

---

*Living document. New rules get appended when a session earns one.*

---

## Part 8 — The Orchestration Patterns

Current as of August 2026. Dynamic Workflows shipped as a research preview on
2026-05-28 and are Claude Code's orchestration layer for work too big for one
agent pass; `/effort ultracode` sends `xhigh` reasoning effort *and* auto-decides
whether a request warrants a workflow. Scale ceiling: 16 concurrent agents, 1,000
per lifetime. Nested subagents are capped at depth 5.

### 49. Name the pattern; don't say "use some subagents"
There are six named patterns, and asking for one by name produces a sharper harness
than any amount of describing it.

| Pattern | What it does | Use when |
|---|---|---|
| **Classify-and-act** | A classifier reads the task, decides its type, routes each kind to the right downstream agent | Mixed inbox of work, one size does not fit |
| **Fan-out-and-synthesize** | Split into many small steps, one agent each, merge at a barrier | The work divides cleanly and you need it whole |
| **Adversarial verification** | For each finding, spawn a separate skeptic whose only job is to refute it | Findings that look plausible and might not be (#20, #23) |
| **Generate-and-filter** | Generate many noisy candidates, then a separate pass filters, dedupes, keeps what holds | Ideation, naming, test-case generation |
| **Tournament** | Agents attempt the same task differently, a judge compares pairwise until one wins | Wide solution space, no obvious right approach (#21) |
| **Loop-until-done** | Size unknown — keep spawning until a stop condition is met | You can't enumerate the work up front (#31) |

*Why:* A named pattern is a specification of the control flow — how many agents,
what each sees, where the barrier is, who judges. "Use subagents" specifies none of
that and gets you the default: a flat fan with no verification step. Note that four
of the six encode rules this document arrived at independently, which is decent
evidence they're load-bearing rather than fashionable.

### 50. Know which isolation you're buying
Workflow agents are **isolated by design** — no inter-agent communication. Agent
Teams have **peer-to-peer messaging** and can renegotiate live.

*Why:* This is the precise fix for the sibling-conflict failure in #41. Isolation is
what makes fan-out cheap and parallel, and it's exactly why two agents can pick
incompatible conventions without noticing. You have two remedies and they cost
differently: a **shared contract file** the isolated agents all read first (cheap,
static, works in a workflow), or **Agent Teams** where they can actually talk
(expensive, dynamic, worth it when the interface can't be settled up front). Choose
deliberately — don't discover at the merge that you needed the other one.
