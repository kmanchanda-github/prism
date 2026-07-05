# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**Prism** — AI-powered incident analysis system. Incidents arrive via UI form or webhooks (Jira, Salesforce). A LangGraph orchestrator fans out to sub-agents (log analysis, code analysis, defect lookup), synthesizes findings into a Markdown report, and presents it in a React UI where engineers can chat with the AI, edit, version, and export the analysis.

See `PLAN.md` for the full architecture, data flow, and phased implementation plan.

## Commands

### Backend

```bash
# First-time setup
cp .env.example .env                    # set LLM_PROVIDER, LLM_MODEL, and matching API key
docker-compose up -d                    # starts Postgres, Redis, API, Celery workers
uv pip install -e ".[anthropic,dev]"    # install with chosen provider + dev tools
# uv pip install -e ".[openai,dev]"     # or openai
# uv pip install -e ".[google,dev]"     # or google
# uv pip install -e ".[bedrock,dev]"    # or bedrock

# Run API only (local, no Docker)
uvicorn src.api.main:app --reload

# Run Celery worker (local)
celery -A src.api.worker.celery_app worker --loglevel=info --concurrency=4

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head

# Tests
pytest
pytest tests/unit/
pytest tests/integration/
pytest --cov=src --cov-report=term

# Lint / format
ruff check src/
ruff format src/
```

### Frontend (ui/)

```bash
cd ui
npm install
npm run dev      # dev server on :5173, proxies /api and /webhooks to :8002 (see docker-compose.yml port remap)
npm run build    # outputs to ui/dist/ — FastAPI serves this
```

## Architecture at a Glance

**Intake paths:**
- `POST /api/analysis` (UI form) → Celery task — **this is the supported demo/grading path**
- `POST /webhooks/jira` (HMAC-validated) or `/generic` (any payload) → Celery task — also real
- `POST /webhooks/salesforce` → returns a `"stub"` status — an extensibility hook, not a wired integration (see below)

**Analysis pipeline** (`src/agents/orchestrator.py`):
`parse_incident → route_decision → [parallel] log/code/defect agents → synthesizer → quality_check → notify`

**Stubs vs. real integrations:** `src/adapters/` follows an abstract-base-class pattern (`base.py`) specifically so new integrations are a drop-in subclass. Several adapters are intentionally left as stubs to demonstrate that surface without a real backend behind them: `SalesforceAdapter` (no file — only the webhook route exists), Splunk/Datadog data sources (no files), Email/Webex notifications, and the workaround-execution approval gate. Don't treat their presence as "incomplete features to finish" without being asked — they're placeholders showing where an implementation would plug in. `LogBundleAdapter`, `JiraAdapter`, `SlackAdapter`, and the evaluator agent (below) are the real, wired examples of the same pattern.

**Evaluation & improvement loop (real, not a stub):** `POST /api/analysis/{id}/evaluate` runs `src/agents/evaluator.py::run_evaluation()` — a real LLM call comparing the AI's analysis against the actual resolution, returning an accuracy score and a one-sentence hint. The hint is persisted (`improvement_hints` table, `src/models/evaluation.py`) and looked up by service in `worker.py` before the *next* matching incident's graph run, then injected into `synthesizer.py`'s prompt — so evaluated runs measurably affect future ones, not just get logged. Optionally, if `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY` are set, the evaluator also attaches its score as LangSmith feedback on the original synthesis trace (`_attach_langsmith_feedback()` in `src/api/routes/evaluation.py`) — this is a no-op if tracing isn't configured.

**Key directories:**
- `src/agents/` — LangGraph nodes (orchestrator, log/code/defect analysts, synthesizer, chat, evaluator)
- `src/adapters/` — pluggable integrations (data sources, incident systems, notifications); add new ones by subclassing `base.py`
- `src/api/routes/` — FastAPI route files (analysis, chat, webhooks, export, actions)
- `src/api/worker.py` — Celery app and `run_analysis_task`
- `src/outputs/exporters/` — PDF (WeasyPrint) and PPTX (python-pptx) generators
- `ui/src/` — React + Vite frontend (components, pages, hooks)

**Adding a new data source adapter:**
1. Subclass `DataSourceAdapter` in `src/adapters/data_sources/your_adapter.py`
2. Enable it in `config.yaml` under `data_sources:`
3. Register it in the orchestrator's `route_decision` logic

**Adding a new incident system:**
1. Subclass `IncidentSystemAdapter` in `src/adapters/incident_systems/your_system.py`
2. Add a webhook route in `src/api/routes/webhooks.py`
3. Set config in `config.yaml` and env vars in `.env`

## LLM Provider

Set `LLM_PROVIDER` and `LLM_MODEL` in `.env`, then install only that provider's package:

| Provider | `LLM_PROVIDER` | Required key | Install extra |
|---|---|---|---|
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `.[anthropic]` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `.[openai]` |
| Google | `google` | `GOOGLE_API_KEY` | `.[google]` |
| AWS Bedrock | `bedrock` | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | `.[bedrock]` |

The factory lives in `src/core/llm.py`. All agents call `get_llm()` — no agent code changes when switching providers.

## Environment Variables

All credentials go in `.env` (see `.env.example`). The app will fail to start without `LLM_PROVIDER`, `LLM_MODEL`, the matching API key, `DATABASE_URL`, and `SECRET_KEY`.

## Phase Status

- **Phase 1 (complete):** Core scaffold, models, LangGraph skeleton, log bundle adapter, all API routes, React UI
- **Phase 2 (complete):** Code+defect agents, full PDF/PPT templates, chat suggested-edit wiring. Splunk/Datadog adapters and Salesforce full impl remain extensibility hooks (see above).
- **Phase 3:** Workaround execution approval gate, Email/Webex notification adapters — still hooks. Per-analysis token/cost is shown in the UI; there's no aggregate cross-analysis dashboard yet.
- **Phase 4 (partially complete):** Evaluator agent + improvement feedback loop — done, including optional LangSmith tracing/feedback. Load testing — not started. Cloud deployment (Hugging Face Spaces) — done.
