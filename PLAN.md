# Prism — Architecture, Design & Implementation Plan

## Problem Statement

Product engineers manually gather incident data from multiple sources, correlate it, and write analysis. This system automates that pipeline: an incident triggers analysis (via webhook or UI form), sub-agents query relevant data sources in parallel, and a synthesis report is generated. Engineers review it via a chat-enabled UI, edit and approve it, then share or export it for technical and executive audiences.

---

## Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Required |
| LLM provider | **Pluggable via `.env`** — `LLM_PROVIDER` + `LLM_MODEL` | Anthropic, OpenAI, Google, AWS Bedrock; swap with two env vars, zero code change. Factory in `src/core/llm.py` |
| Agent framework | **LangGraph** | Native parallel fan-out via `Send` API; explicit state machine; `interrupt` for approval gates; Postgres-backed checkpointer for resume/re-run |
| API layer | **FastAPI** | Async-native; SSE for chat streaming; OpenAPI docs out of the box |
| Task queue | **Celery + Redis** | Decouples HTTP from long-running analysis; enforces 100-concurrent ceiling at the worker pool level |
| UI | **React + Vite + TypeScript** | Portable SPA; FastAPI serves the built static files — single container, works locally and on any cloud |
| Component library | **shadcn/ui + Tailwind CSS** | Pre-built accessible components; no design system from scratch |
| Database | **PostgreSQL + SQLAlchemy + Alembic** | Incident records, analysis versions, chat history, token metrics |
| Vector store | **ChromaDB** (local) / **Qdrant** (hosted) | RAG over runbooks and code docs; swap via adapter |
| PDF export | **WeasyPrint** | HTML template → PDF; handles CSS/branding cleanly |
| PPT export | **python-pptx** | Slide deck generation from templates |
| Notifications | Slack SDK, Webex SDK, SendGrid | Pluggable via adapter |
| Packaging | `uv` + `pyproject.toml` | Fast, reproducible |

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        UI Layer                                  │
│         React + Vite (served as static files by FastAPI)         │
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐ │
│  │  Incident Form  │    │         Report Viewer                │ │
│  │  (manual path)  │    │  Analysis · Edit · Version History   │ │
│  └────────┬────────┘    │  Chat Panel (SSE stream)             │ │
│           │             │  Action Bar · Export buttons         │ │
│           │             └──────────────────────────────────────┘ │
└───────────┼──────────────────────────────────────────────────────┘
            │ REST / SSE
┌───────────▼──────────────────────────────────────────────────────┐
│                        FastAPI Gateway                           │
│                                                                  │
│  POST /api/analysis          GET  /api/analysis/{id}            │
│  PATCH /api/analysis/{id}    GET  /api/analysis/{id}/versions   │
│  POST /api/analysis/{id}/chat                                   │
│  POST /api/analysis/{id}/export                                 │
│  POST /api/analysis/{id}/action                                 │
│  POST /webhooks/jira         POST /webhooks/salesforce          │
│  POST /webhooks/generic                                         │
└───────────┬──────────────────────────┬───────────────────────────┘
            │ enqueue                  │ read results
┌───────────▼──────────┐   ┌──────────▼───────────────────────────┐
│   Celery Worker Pool │   │            PostgreSQL                │
│   (concurrency=100)  │   │                                      │
│                      │   │  incidents · analysis_versions       │
│  Redis (broker)      │   │  chat_history · token_metrics        │
└───────────┬──────────┘   │  action_audit_log                   │
            │              └──────────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────────────┐
│              Orchestrator Agent  (LangGraph StateGraph)           │
│                                                                  │
│  parse_incident → route_decision → [parallel fan-out via Send]  │
│       → quality_check → notify on complete                      │
└──┬──────────────────┬───────────────────────┬────────────────────┘
   ▼                  ▼                       ▼
Code Agent        Log Agent             Defect Agent
(repo/git)   (bundle/Splunk/Datadog)   (Jira/Salesforce)
   │                  │                       │
   └──────────────────┴───────────────────────┘
                      │ partial results
┌─────────────────────▼────────────────────────────────────────────┐
│                   Synthesizer Agent                              │
│      Root cause · Workaround · Recommended actions               │
│      Confidence score · Token usage per sub-agent               │
└─────────────────────┬────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────┐
│                 Output & Action Layer                            │
│                                                                  │
│  • Report stored as AnalysisVersion v0 (AI-generated)           │
│  • Notification sent: Slack/Email/Webex with link to UI         │
│  • Engineer reviews, chats with AI, edits → v1, v2...           │
│  • Workaround execution (approval gate via LangGraph interrupt)  │
│  • Export: PDF Technical · PDF Executive · PPT Executive · PPT Customer │
└─────────────────────┬────────────────────────────────────────────┘
                      │ on-demand, post-closure
┌─────────────────────▼────────────────────────────────────────────┐
│            Evaluation & Improvement Agent                        │
│  Scores prior analysis vs actual resolution                     │
│  Emits prompt-improvement hints → improvement_reports table     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Incident Intake: Two Paths, One Pipeline

### Path A — Manual (UI Form)
```
Engineer fills form → POST /api/analysis → Celery job → analysis runs → report in UI
```

### Path B — Automatic (Webhook)
```
Jira/Salesforce creates ticket
  → fires webhook → POST /webhooks/jira
    → validate HMAC signature
      → IncidentSystemAdapter.parse_webhook() → Incident model
        → Celery job → analysis runs
          → NotificationAdapter.send(link="/analysis/{id}")
            → Engineer clicks link → reviews report in UI
```

Trigger rules are config-driven — not every ticket fires analysis:
```yaml
incident_systems:
  jira:
    intake_mode: webhook          # or: polling
    polling_interval_seconds: 60
    webhook_secret: ${JIRA_WEBHOOK_SECRET}
    trigger_on:
      issue_types: [Bug, Incident]
      priorities: [P0, P1, P2]
      projects: [PROD, INFRA]
      status_transitions: [Open, "In Progress"]
```

Polling fallback (Celery Beat) uses the same adapter and `Incident` model — just a different trigger mechanism.

---

## Plugin / Adapter Design

All external integrations implement an abstract base. Adding a new source = one new file + one config.yaml entry.

```python
class DataSourceAdapter(ABC):
    async def fetch(self, incident: Incident, context: dict) -> DataChunk: ...

class IncidentSystemAdapter(ABC):
    async def get_incident(self, id: str) -> Incident: ...
    async def parse_webhook(self, payload: dict, headers: dict) -> Incident: ...
    async def update_incident(self, id: str, analysis: Analysis) -> None: ...
    async def create_incident(self, incident: Incident) -> str: ...
    def validate_signature(self, payload: bytes, headers: dict) -> bool: ...

class NotificationAdapter(ABC):
    async def send(self, message: str, link: str, summary: str, config: dict) -> None: ...
```

| Category | Adapters shipped |
|---|---|
| Data sources | `LogBundleAdapter`, `SplunkAdapter`, `DatadogAdapter` |
| Incident systems | `JiraAdapter`, `SalesforceAdapter` |
| Notifications | `SlackAdapter`, `WebexAdapter`, `EmailAdapter` |

---

## Agent State Machine (LangGraph)

```
START
  └─► parse_incident
        └─► route_decision              ← LLM picks which agents to activate
              └─► [parallel Send API]
                    ├─► code_agent      ← conditional
                    ├─► log_agent       ← always for Phase 1
                    └─► defect_agent    ← conditional
                          └─► synthesizer
                                └─► quality_check   ← retry if confidence < threshold
                                      └─► notify
                                            └─► END
```

Key LangGraph features:
- `StateGraph` with typed `AnalysisState` (Pydantic)
- `Send` API for dynamic parallel fan-out to N sub-agents
- `interrupt` node for workaround approval gate
- Postgres-backed `checkpointer` — analysis survives worker crash and supports re-run from any node

---

## Chat Agent

Scoped to a specific analysis. Full context injected as system prompt:

```
System:
  Incident: {incident metadata + description}
  Sub-agent findings: {raw outputs from code/log/defect agents}
  Current report: {latest AnalysisVersion}
  Conversation so far: {chat_history}

User: "Why did you rule out a DB pool issue?"
```

Response may include a `suggested_edit` alongside prose:
```json
{
  "message": "The pool utilization was at 42%...",
  "suggested_edit": { "field": "root_cause", "value": "..." }
}
```

Engineer accepts/rejects the suggestion. Chat responses stream via SSE.

---

## Analysis Versioning

Original AI output is never overwritten. Every edit (manual or chat-suggested) creates a new version.

```python
class AnalysisVersion(BaseModel):
    analysis_id: str
    version: int                  # 0 = AI original
    root_cause: str
    workaround: str
    recommended_actions: list[Action]
    edited_by: str                # "ai" or engineer email
    edit_source: Literal["ai_generated", "chat_suggestion", "manual_edit"]
    created_at: datetime
```

Share and Export always use the **latest version**. The UI shows a version history tab with diffs.

---

## Data Models

```python
class Incident(BaseModel):
    id: str
    source: Literal["manual", "jira", "salesforce", "generic"]
    title: str
    description: str
    severity: Literal["P0", "P1", "P2", "P3"]
    metadata: dict                # product, version, customer, env, etc.
    sources_hint: list[str] | None

class AnalysisReport(BaseModel):
    id: str
    incident_id: str
    status: Literal["pending", "running", "complete", "failed"]
    current_version: int
    confidence_score: float
    token_usage: TokenMetrics
    sub_reports: list[SubReport]
    created_at: datetime
    rerun_count: int

class TokenMetrics(BaseModel):
    orchestrator: int
    code_agent: int
    log_agent: int
    defect_agent: int
    synthesizer: int
    chat_total: int
    total: int
    estimated_cost_usd: float

class ChatMessage(BaseModel):
    analysis_id: str
    role: Literal["user", "assistant"]
    content: str
    suggested_edit: dict | None
    created_at: datetime
```

---

## Export Templates

Two audience types, three formats:

| Template | Format | Audience | Content |
|---|---|---|---|
| `technical` | PDF | Engineers | Full analysis, log refs, code pointers, appendix |
| `executive` | PDF or PPT | Leadership | Business impact, plain-language root cause, action items |
| `customer` | PPT | External | What happened, what we did, prevention plan |

PPT executive slide structure:
1. Incident title + severity + date
2. Business impact (what was affected, duration)
3. Root cause (one diagram or paragraph)
4. Resolution timeline
5. Prevention actions (owner + due date)
6. Open items

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  INC-4821 · P1 · Payment service timeout · via Jira              │
├────────────────────────────┬─────────────────────────────────────┤
│   ANALYSIS REPORT          │   CHAT WITH AI                      │
│                            │                                     │
│  Root Cause            ✏   │  > Why was DB pool ruled out?       │
│  ──────────────────────    │                                     │
│  [text — editable]         │  AI: Pool utilization was 42%...    │
│                            │  [Apply suggested edit ✓]           │
│  Workaround            ✏   │                                     │
│  ──────────────────────    │  > Update root cause to reflect?    │
│  [text — editable]         │                                     │
│                            │  AI: Updated. [Apply ✓] [Dismiss ✗] │
│  Recommended Actions   ✏   │                                     │
│  [ ] Action 1              │  [_____________________________]    │
│  [ ] Action 2              │  [Send]                             │
│                            │                                     │
├────────────────────────────┴─────────────────────────────────────┤
│  [Approve & Execute Workaround]  [Re-run]  [Edit & Re-run]       │
│  [Email]  [Slack]  [Webex]                                       │
│  [PDF Technical]  [PDF Executive]  [PPT Executive]  [PPT Customer]│
│  Version: v0 (AI) · v1 (you, 10m ago)  [View Diff]              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
Prism/
├── src/
│   ├── agents/
│   │   ├── orchestrator.py       # LangGraph StateGraph
│   │   ├── code_analyst.py
│   │   ├── log_analyst.py
│   │   ├── defect_analyst.py
│   │   ├── synthesizer.py
│   │   ├── chat_agent.py         # Clarification chat
│   │   └── evaluator.py
│   ├── adapters/
│   │   ├── base.py
│   │   ├── data_sources/
│   │   │   ├── log_bundle.py
│   │   │   ├── splunk.py
│   │   │   └── datadog.py
│   │   ├── incident_systems/
│   │   │   ├── jira.py
│   │   │   └── salesforce.py
│   │   └── notifications/
│   │       ├── slack.py
│   │       ├── webex.py
│   │       └── email.py
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── analysis.py
│   │   │   ├── chat.py
│   │   │   ├── actions.py
│   │   │   ├── webhooks.py
│   │   │   └── export.py
│   │   └── worker.py             # Celery app + tasks
│   ├── outputs/
│   │   ├── exporters/
│   │   │   ├── pdf_technical.py
│   │   │   ├── pdf_executive.py
│   │   │   ├── pptx_executive.py
│   │   │   └── pptx_customer.py
│   │   └── report_generator.py
│   ├── models/
│   │   ├── incident.py
│   │   ├── report.py
│   │   ├── chat.py
│   │   └── metrics.py
│   └── core/
│       ├── config.py
│       ├── database.py
│       └── token_tracker.py
├── ui/                           # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── IncidentForm.tsx
│   │   │   ├── ReportViewer.tsx
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── ActionBar.tsx
│   │   │   └── VersionHistory.tsx
│   │   ├── pages/
│   │   │   ├── Submit.tsx
│   │   │   └── Analysis.tsx
│   │   ├── hooks/
│   │   │   ├── useAnalysis.ts
│   │   │   └── useChat.ts
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config.yaml
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

---

## API Endpoints

```
POST   /api/analysis                      # Submit incident (manual path)
GET    /api/analysis/{id}                 # Get report + status
PATCH  /api/analysis/{id}                 # Save edited version
GET    /api/analysis/{id}/versions        # Version list with diffs
POST   /api/analysis/{id}/chat            # Send chat message (SSE stream)
GET    /api/analysis/{id}/chat            # Full conversation history
POST   /api/analysis/{id}/export          # Generate PDF/PPTX download
POST   /api/analysis/{id}/action          # Execute action (workaround, notify, share)
POST   /webhooks/jira                     # Jira webhook intake
POST   /webhooks/salesforce               # Salesforce webhook intake
POST   /webhooks/generic                  # Generic webhook intake
GET    /api/metrics/token-usage           # Token usage dashboard data
```

---

## Implementation Phases

### Phase 1 — Core Pipeline (PoC)
- [x] Project scaffold: pyproject.toml, docker-compose, Dockerfile, config.yaml
- [x] Core modules: config, database, token tracker
- [x] Data models + Alembic migrations
- [x] Adapter base classes + LogBundleAdapter
- [x] Skeleton LangGraph orchestrator → log_agent → synthesizer
- [x] FastAPI: all route files (analysis, chat, webhooks, export, actions)
- [x] Celery worker task
- [x] React UI scaffold: IncidentForm, ReportViewer, ChatPanel, ActionBar, VersionHistory

### Phase 2 — Pluggable Adapters, Chat & Export
- [ ] SplunkAdapter, DatadogAdapter — not started
- [x] JiraAdapter — webhook intake + HMAC signature validation
- [ ] JiraAdapter polling mode, SalesforceAdapter — `config.yaml` has an `intake_mode: polling` option and `POST /webhooks/salesforce` exists as a route, but neither a poller nor a `SalesforceAdapter` class is implemented; the Salesforce route returns `{"status": "not_implemented"}`
- [x] CodeAnalystAgent, DefectAnalystAgent
- [x] Adapter registry loaded from config.yaml — each data-source adapter reads its own `config.yaml` section via `get_yaml_config()`
- [x] Chat agent with SSE streaming + suggested edits
- [x] Analysis version history in UI — [ ] diff view — `VersionHistory.tsx` lists versions (author, source, timestamp) but does not render a diff between them
- [x] PDF technical + executive exporters (WeasyPrint)
- [x] PPT executive + customer exporters (python-pptx)
- [ ] Re-run from any LangGraph checkpoint — orchestrator calls `.compile()` with no checkpointer configured

### Phase 3 — Actions, Notifications & Metrics
- [x] SlackAdapter — [ ] WebexAdapter, EmailAdapter — not started
- [ ] Workaround execution with approval gate (LangGraph interrupt) — `POST /analysis/{id}/action` currently just logs "requires Phase 3 implementation"
- [x] Action audit log — every action request is recorded to `ActionAuditORM`, including the not-yet-implemented ones
- [ ] Token usage dashboard in UI (per-analysis + aggregate trends) — not started
- [x] Notification on analysis complete — Slack only, sent from `worker._run()` on success

### Phase 4 — Evaluation Agent & Scale
- [ ] EvaluatorAgent — on-demand post-closure scoring — `evaluator.py` is a one-line `NotImplementedError` stub, not wired into the graph
- [ ] Prompt improvement report — not started
- [ ] Celery concurrency tuning + rate limiting — `worker_max_tasks_per_child=50` is set; concurrency is 4 in `docker-compose.yml`, not the 100 referenced under Scalability Notes below; no rate limiting implemented
- [ ] Load test: 100 concurrent analyses — not started
- [x] Hugging Face Spaces / cloud deployment config — `Dockerfile.huggingface` and `hf-README.md`

---

## Scalability Notes

- Celery `--concurrency=100`; `CELERYD_MAX_TASKS_PER_CHILD=50` prevents memory leaks from large log bundles.
- LangGraph Postgres checkpointer — analysis survives worker restart and supports partial re-run.
- Log bundles chunked with sliding-window summarization to stay within context limits.
- Token tracker aggregates per sub-agent so the most expensive agent can be optimized independently.
- Chat history is summarized after 20 turns to avoid unbounded context growth.

---

## Guard Rails

- Workaround execution always requires engineer approval (`interrupt` node).
- All adapter credentials in environment variables; never in config.yaml or code.
- Sub-agent outputs validated against schema before synthesis — malformed results trigger a retry.
- Evaluation agent is read-only by default; cannot modify original analysis records.
- Webhook signatures validated (HMAC) before any payload is processed.
