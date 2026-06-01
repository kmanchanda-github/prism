# Prism — Prompt Design Documentation

This document explains the system prompt for each LangGraph agent: what it instructs the LLM to do, what output format it expects, and the reasoning behind the design choices.

---

## 1. Orchestrator — Route Decision

**File:** `src/agents/orchestrator.py` → `route_decision()`

**Prompt:**
```
You are an incident triage router. Given incident metadata and description,
decide which analysis agents to activate.
Reply with a JSON list from: ["log_agent", "code_agent", "defect_agent"].
Always include log_agent if log data may be relevant.
Example: ["log_agent", "defect_agent"]
```

**Expected output:** A JSON array, e.g. `["log_agent", "code_agent", "defect_agent"]`

**Design rationale:**
- **Minimal instruction surface.** The router only needs to pick from a fixed set of three agents — a short, unambiguous prompt reduces the chance of hallucinated agent names.
- **Biased toward log_agent.** Logs are available for almost every production incident, so the prompt instructs the LLM to default to including `log_agent` unless there's a clear reason not to. This prevents the common failure mode of the router skipping log analysis on vague descriptions.
- **JSON-only reply.** Asking for a bare JSON array (not markdown-wrapped) makes regex extraction trivial (`re.search(r"\[.*?\]", ...)`). A fallback to `["log_agent"]` handles parse failures.
- **Inputs:** title, severity, description, metadata — enough signal to route without requiring a full log fetch upfront.

---

## 2. Log Analyst

**File:** `src/agents/log_analyst.py`

**Prompt:**
```
You are a log analysis expert. Analyze the provided logs for the given incident.
Identify error patterns, anomalies, timing issues, and root cause indicators.
Be specific about line references. Conclude with a confidence score (0.0-1.0)
that these logs contain enough signal for root cause determination.
```

**Expected output:** Free-form analysis prose ending with a confidence statement. Confidence is currently hardcoded at `0.7` post-response (a Phase 3 improvement is to parse it from the LLM output via structured output mode).

**Design rationale:**
- **"Be specific about line references"** — without this instruction, LLMs tend to summarise logs generically. Requiring line-level specificity produces findings that are citable in the final report.
- **Confidence score in the prompt** — even though the current code hardcodes `0.7`, the instruction primes the LLM to reason about signal quality. Future versions will parse it for use in `quality_check`.
- **Log chunking** — the adapter caps context at 10 chunks × 50,000 chars each. The prompt is designed to work with partial log data; it asks for "patterns and indicators" rather than assuming completeness.

---

## 3. Code Analyst

**File:** `src/agents/code_analyst.py`

**Prompt:**
```
You are a senior software engineer conducting a code change review for an incident.
You will be given a git diff or code change summary and incident context.
Identify:
  1. Which specific code or config changes are most likely to have caused the incident.
  2. Any missing safeguards (tests, validation, rollback gates) that would have prevented it.
  3. The risk profile of the change (scope, blast radius, reversibility).
Be specific — reference file names, line numbers, and config keys from the diff.
Conclude with a confidence score (0.0–1.0) that this change is the root cause.
```

**Expected output:** Structured prose with three sections as numbered above, concluding with a confidence statement.

**Design rationale:**
- **Three-part structure** ensures the agent covers both the proximate cause (what changed) and the process failure (why it wasn't caught), which together give engineers actionable findings.
- **"Reference file names, line numbers, and config keys"** — same reason as the log analyst: specificity makes the finding citable. Without this, the LLM produces vague summaries like "the configuration was changed."
- **"Risk profile"** framing (scope, blast radius, reversibility) is standard incident vocabulary. Using it in the prompt produces output that maps directly onto post-mortem templates.
- **Data source:** the `CodeChangesAdapter` auto-discovers the diff by matching `incident.metadata.deploy_sha` to files in `demo/code/`. Falls back to metadata hints if no diff file exists.

---

## 4. Defect Analyst

**File:** `src/agents/defect_analyst.py`

**Prompt:**
```
You are a defect analyst cross-referencing an incident against a database of known issues.
You will be given known defect records (JSON) and incident context.
Identify:
  1. Which known defects match or are related to this incident, and how closely.
  2. Whether this incident is a recurrence of a previously seen issue.
  3. Whether any open defects (status='open' or 'known') have documented workarounds
     that should have prevented this, and whether they were applied.
Reference defect IDs (e.g. DEFECT-1041) explicitly.
Conclude with a confidence score (0.0–1.0) that a known defect is the root cause.
```

**Expected output:** Analysis prose referencing specific defect IDs and their match strength.

**Design rationale:**
- **Recurrence framing** is the most valuable output of defect analysis. If the incident is DEFECT-1041 happening for the third time, that changes the recommended action from "fix the config" to "fix the process that keeps allowing this config." The prompt explicitly asks for recurrence detection.
- **"Were workarounds applied?"** — this asks the LLM to reason about whether documented mitigations were ignored, surfacing process failures rather than just technical ones.
- **Pre-filtered input:** the `DefectDbAdapter` scores and filters defects by service name + keyword match before sending to the LLM, keeping the context window focused and reducing noise.
- **Explicit ID references** — requiring the LLM to cite `DEFECT-XXXX` IDs makes the output linkable to the actual defect tracker.

---

## 5. Synthesizer

**File:** `src/agents/synthesizer.py`

**Prompt:**
```
You are a senior site reliability engineer synthesizing findings from multiple analysis agents.

Given sub-agent findings, produce a JSON object with exactly these keys:
{
  "root_cause": "...",
  "workaround": "...",
  "recommended_actions": [
    {"id": "1", "title": "...", "description": "...", "priority": "high|medium|low",
     "type": "defect_fix|product_improvement|process|monitoring", "owner": null, "due_date": null}
  ],
  "confidence_score": 0.0
}

confidence_score: 0.0-1.0 reflecting how certain you are of the root cause.
Be concrete and actionable. Do not hedge excessively.
```

**Expected output:** A JSON object matching the schema above, parseable by `re.search(r"\{.*\}", ...)`.

**Design rationale:**
- **Strict JSON schema in the prompt** — the synthesizer output feeds directly into the database ORM and the UI. Asking for a specific schema (rather than asking the LLM to "summarise") produces machine-parseable output without a separate structured-output API call.
- **`"Do not hedge excessively"`** — LLMs default to hedging ("this may possibly be related to..."). SREs need concrete conclusions they can act on. This instruction measurably improves actionability.
- **`type` enum on actions** (`defect_fix | product_improvement | process | monitoring`) — this vocabulary maps directly to how engineering teams classify post-mortem action items, making export to Jira/Linear straightforward.
- **Retry loop:** the `quality_check` node in the orchestrator compares `confidence_score` against the `confidence_threshold` in `config.yaml` (default `0.7`). If below threshold, the graph re-runs `route_decision` with up to `max_retries=2` additional passes.
- **Fallback:** if the LLM returns prose without JSON (e.g. "I cannot determine the root cause"), `run_synthesis` falls back gracefully — the prose becomes `root_cause`, and `confidence_score` is set to `0.3` to trigger a retry.

---

## 6. Chat Agent

**File:** `src/agents/chat_agent.py`

**Prompt (template, injected at runtime):**
```
You are an AI assistant helping a product engineer understand and refine an incident analysis.

You have full context:
- Incident metadata and description
- Raw findings from each analysis agent (logs, code, defects)
- The current synthesized analysis report
- The conversation so far

Answer questions clearly. If your answer suggests a change to the root cause, workaround, or
recommended actions, include a suggested_edit in your response using this exact JSON block:

<suggested_edit>
{"field": "root_cause|workaround|recommended_actions", "value": "..."}
</suggested_edit>

Only include a suggested_edit when a specific field change is warranted. Do not suggest edits
for every response.
```

**At runtime, the full system message also includes:**
- `--- INCIDENT ---` block with title, description, and metadata
- `--- SUB-AGENT FINDINGS ---` block with raw findings from each agent
- `--- CURRENT REPORT ---` block with root cause, workaround, and actions

**Expected output:** Conversational prose, optionally containing one `<suggested_edit>` XML block.

**Design rationale:**
- **XML tag for suggested edits, not JSON-only** — embedding a JSON block inside a JSON response causes escaping issues. An XML-style `<suggested_edit>` tag is easy to extract with `re.search(r"<suggested_edit>(.*?)</suggested_edit>", ..., re.DOTALL)` and survives markdown rendering without breaking.
- **"Only include a suggested_edit when a specific field change is warranted"** — without this guard, the LLM suggests edits on almost every response (it's eager to be helpful). The instruction reduces noise so engineers only see edit prompts when the AI has a concrete, actionable change to propose.
- **Full sub-agent context injected** — the chat agent receives the raw findings from log/code/defect agents, not just the synthesized summary. This allows it to answer specific questions like "what did the log agent find at 14:32?" without hallucinating.
- **Streaming:** `stream_response()` yields tokens via SSE so the UI can show typing indicators. `_parse_suggested_edit()` runs on the full assembled response after streaming completes.

---

## Prompt Tuning Notes

| Agent | Temperature | Max tokens | Notes |
|---|---|---|---|
| Route decision | 0.2 | 8192 | Low temp for deterministic routing |
| Log analyst | 0.2 | 8192 | Low temp for factual log reading |
| Code analyst | 0.2 | 8192 | Low temp for diff analysis |
| Defect analyst | 0.2 | 8192 | Low temp for factual matching |
| Synthesizer | 0.2 | 8192 | Low temp to reduce JSON schema drift |
| Chat agent | 0.2 | 8192 | Slightly higher acceptable; clarity > creativity |

All defaults are set in `config.yaml` under `llm.temperature` and `llm.max_tokens` and can be overridden per-call via `get_llm(temperature=..., max_tokens=...)`.
