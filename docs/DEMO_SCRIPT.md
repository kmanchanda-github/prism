# Prism — Video Demo Script (target: 7–8 min, fits the 5–10 min window)

Word-for-word narration. `[Action: ...]` lines are what you do on screen while speaking the line above or below them — practice the timing once before recording. LLM provider is **OpenAI (gpt-4o)**.

---

## 0:00–0:20 — Cold open

> "When production breaks, engineers spend the first hour just gathering information — pulling logs, checking recent deploys, searching old tickets — before they've even started diagnosing the problem. Prism is an AI system that does that gathering and diagnosis automatically, in parallel, in about 30 seconds."

`[Action: title card or the Prism hero section from project-report-v3.html on screen]`

---

## 0:20–1:00 — The problem, in one breath

> "Three things make incident response slow and inconsistent. First, manual correlation — engineers pull logs from one system, defects from another, and code diffs from a third, by hand, every time. Second, inconsistent quality — a senior engineer catches signals a junior one misses. Third, sharing overhead — the same findings get rewritten three times: for engineers, for leadership, and for customers. Prism automates the first problem, reduces the second, and solves the third with one-click exports."

`[Action: scroll to "The Problem" section of the report, or just talk over the UI]`

---

## 1:00–1:50 — Architecture, fast

> "Here's how it works. An incident comes in — either through this UI form, or automatically via a Jira webhook. That hits a FastAPI backend, which hands it to a background worker. A LangGraph orchestrator reads the incident and decides which specialist agents to activate. Then — and this is the important part — the log agent, the code agent, and the defect agent all run *in parallel*, not one after another. Each one is a real LLM call, backed by real data: the log agent reads actual log files, the code agent reads the actual git diff for the deploy that shipped, and the defect agent searches a database of known issues. A synthesizer agent then merges their three independent findings into one root cause, a workaround, and a prioritized action list — with a confidence score. If that confidence is too low, it automatically retries."

`[Action: show the System Architecture diagram from project-report-v3.html — the diagram makes "real vs. hook" visually obvious as you talk]`

---

## 1:50–2:20 — Submit the incident

> "Let's run it live. I'm going to submit the exact incident this system was built to diagnose: a checkout service that started timing out on payment requests."

`[Action: open the Prism UI Submit form]`

> "Title, description, severity — P1 — and the metadata: which service, which deploy SHA rolled out right before this started. That deploy SHA is the thread the code agent is going to pull on in a second."

`[Action: fill the form with the demo incident — title "Checkout service timeout spike — payment failures", the full description, severity P1, metadata service=checkout-service, deploy_sha=d9f3a1c. Click Run Analysis.]`

> "That's it. No log files to attach, no ticket to cross-reference by hand — just describe what happened."

---

## 2:20–2:45 — Waiting, briefly

`[Action: show the polling/loading state on the Analysis page]`

> "While that runs, three agents are working in parallel against real data: a log bundle from that incident window, the actual code diff for deploy d9f3a1c, and a known-issues database with past incidents on this same service. This normally takes twenty to thirty seconds."

---

## 2:45–4:15 — The report

`[Action: report has loaded — walk through root cause, workaround, actions]`

> "And it's done. Root cause, workaround, and four recommended actions, generated from scratch by the model — not a template. Let's look at what actually produced this."

`[Action: expand "Agent Findings"]`

> "This is the part I want to slow down on, because these confidence scores are not hardcoded — each agent states its own confidence in plain text, and Prism parses it out of the response. The log agent found the actual error spike in the checkout service log at 14:32 UTC, cross-referenced it against the Postgres and deploy logs, and reports high confidence. The code agent read the real diff for d9f3a1c and found the actual change: the database connection pool's maximum size was reduced from 20 to 5. And the defect agent searched the known-issues database and found a closely related past incident. Three independent agents, three pieces of *real* evidence, merged into one conclusion."

---

## 4:15–5:15 — Chat with the AI

`[Action: click into the Chat panel]`

> "Engineers can also just ask the AI questions instead of reading templates. Let me ask it something a reviewer would actually want to know."

`[Action: type and send: "Why do you think the pool size change caused this instead of something on the payment gateway side?"]`

> "It answers with the same context the agents had — the logs, the diff, the defect match — not a fresh guess. And if its answer implies the report should change, it proposes a specific edit instead of just talking about it."

`[Action: if a suggested_edit appears, click Apply — otherwise narrate: "When it proposes an edit, I can apply or dismiss it right here, and that creates a new version — the original AI output is never overwritten."]`

---

## 5:15–6:00 — Version history

`[Action: navigate to a pre-seeded, richer example if you have one — otherwise show the version history panel on this analysis]`

> "Every edit — whether I typed it manually or accepted an AI suggestion — creates a new version. Version zero is always the original AI output, untouched. That matters for trust: if I disagree with an edit later, the AI's original reasoning is still right here, not overwritten."

---

## 6:00–6:35 — Export

`[Action: open the Action Bar, trigger a PDF export]`

> "And because the same report needs to reach three different audiences, Prism generates all of them from one source: a technical PDF with the full findings for engineers, an executive summary in plain language, and a slide deck for customer-facing updates — no manual rewriting."

`[Action: show the downloaded PDF briefly]`

---

## 6:35–7:15 — Tech stack and what's a hook vs. what's real

> "Under the hood: LangGraph for the agent orchestration, FastAPI and Celery for the async pipeline, React for the UI, and the LLM provider is fully pluggable — this demo is running on OpenAI's gpt-4o, but swapping to Anthropic, Google, or Bedrock is a two-line config change, zero code changes. I'll also be upfront about scope: a few integration points — Salesforce intake, Email and Webex notifications, a workaround-approval gate, and a post-closure evaluator agent — are intentionally built as extensibility hooks. The interface and the abstract base class are real and match the ones Jira and Slack use; there's just no backend wired behind them yet. That's a deliberate scoping decision, documented as such, not something I'm hiding."

`[Action: show the Pluggable Adapter Map or Deliverables table from the report, which color-codes real vs. hook]`

---

## 7:15–7:45 — Close

> "That's Prism: three agents working in parallel against real evidence, synthesized into one report, refined through conversation, and exported for whoever needs to read it. Thanks for watching."

`[Action: end on the report or the architecture diagram]`

---

## Pre-recording checklist

- [ ] `.env` has a real `OPENAI_API_KEY` (already set for local testing) and `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o`
- [ ] `docker compose up -d` — confirm `prism-api-1` and `prism-worker-1` are both `Up` (not `Exited`)
- [ ] Submit one throwaway test incident before recording to confirm the pipeline completes in under ~30s and confidence lands above the 0.7 retry threshold — avoids an on-camera retry loop
- [ ] If using the pre-seeded historical analysis for the Version History beat (Segment 5:15–6:00), run the seed script first and note its analysis ID
- [ ] Close any unrelated browser tabs/bookmarks bar — the UI runs at `localhost:5173` (or wherever the Vite dev server lands)
- [ ] Have a fallback: if the live LLM call is slow or a rate limit hits, cut to the pre-seeded analysis and narrate over it instead
