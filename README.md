# Prism — AI-Powered Incident Analysis Platform

Prism ingests production incidents, runs a multi-agent LangGraph pipeline to analyse logs, code changes, and known defects, then delivers a structured root-cause report with recommended actions. Engineers can chat with the AI, edit the report, track version history, and export to PDF or PPTX.

---

## Quick Demo (5 minutes)

> Requires the stack running (see [Quick Start](#quick-start) below). A synthetic P1 incident with logs, a git diff, and a known-defects database is included in `demo/`.

**1. Submit the incident:**

```bash
curl -s -X POST http://localhost:8000/api/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Checkout service timeout spike — payment failures",
    "severity": "P1",
    "description": "Starting ~14:32 UTC, checkout service returned 504s on ~40% of payment requests. Error rate went from 0.2% to 38%. Rolled back deploy d9f3a1c at 15:05, recovered by 15:12.",
    "metadata": {
      "service": "checkout-service",
      "environment": "production",
      "deploy_sha": "d9f3a1c",
      "on_call_engineer": "priya@example.com",
      "customer_impact": "~2400 failed transactions"
    },
    "sources_hint": ["log_bundle"]
  }' | python3 -m json.tool
```

**2. Copy the `id` from the response, then poll until `status` is `complete`:**

```bash
curl -s http://localhost:8000/api/analysis/<id> | python3 -m json.tool
```

**3. Open the UI** at http://localhost:5173/analysis/`<id>` to:
- Read the AI-generated root cause, workaround, and recommended actions
- Expand **Agent Findings** to see what each of the three agents found
- Chat with the AI (`"What deploy caused this?"`, `"Suggest a process improvement"`)
- Accept a suggested edit → watch version history increment
- Export to PDF or PPTX via the action bar

**Expected analysis:** The three agents (log, code, defect) will independently identify the `DB_POOL_SIZE` reduction in deploy `d9f3a1c`, cross-reference it against `DEFECT-1041` in the known-issues database, and the synthesizer will produce a root cause linking the config change to connection pool exhaustion.

---

## Architecture

```
Incident (UI form or Jira/Salesforce webhook)
  └─► POST /api/analysis ─► Celery task
        └─► LangGraph orchestrator
              ├─ parse_incident
              ├─ route_decision  (LLM picks agents)
              ├─ [parallel] log_agent · code_agent · defect_agent
              ├─ synthesizer     (LLM → root_cause + workaround + actions)
              ├─ quality_check   (retry if confidence < threshold)
              └─ notify          (Slack / email)
        └─► React UI: report viewer · chat · version history · export
```

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Python 3.12+
- Node 18+ (frontend)
- An LLM API key (Anthropic recommended)

### 1. Environment

```bash
cp .env.example .env
# Edit .env — set LLM_PROVIDER, LLM_MODEL, and your API key at minimum
```

| Variable | Required | Example |
|---|---|---|
| `LLM_PROVIDER` | ✅ | `anthropic` |
| `LLM_MODEL` | ✅ | `claude-sonnet-4-6` |
| `ANTHROPIC_API_KEY` | ✅ (if anthropic) | `sk-ant-...` |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://prism:prism@localhost:5432/prism` |
| `SECRET_KEY` | ✅ | any 32+ char random string |
| `CELERY_BROKER_URL` | ✅ | `redis://localhost:6379/0` |

### 2. Start infrastructure

```bash
docker-compose up -d        # Postgres + Redis
alembic upgrade head        # Run DB migrations
```

### 3. Backend

```bash
# Install (pick one provider):
uv pip install -e ".[anthropic,dev]"
# uv pip install -e ".[openai,dev]"

# API server
uvicorn src.api.main:app --reload

# Celery worker (separate terminal)
celery -A src.api.worker.celery_app worker --loglevel=info --concurrency=4
```

### 4. Frontend

```bash
cd ui
npm install
npm run dev      # http://localhost:5173 — proxies /api to :8000
```

---

## Running a Demo Analysis

1. Open http://localhost:5173
2. Fill in the Submit form with a P1 incident (title, description, severity)
3. The UI redirects to the Analysis page and polls until complete
4. Chat with the AI, accept edits, view version history, export to PDF/PPTX

### Demo with synthetic log bundle

A pre-built incident scenario is included in `demo/`:

```bash
# The log bundle zip + code diff + known defects are already in demo/
ls demo/logs/incident-checkout-20250530.zip
ls demo/code/d9f3a1c.diff
ls demo/defects/known_issues.json
```

Submit via API directly:

```bash
curl -X POST http://localhost:8000/api/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Checkout service timeout spike — payment failures",
    "severity": "P1",
    "description": "Starting ~14:32 UTC, checkout service returned 504s on ~40% of payment requests. Error rate went from 0.2% to 38%. Rolled back deploy d9f3a1c at 15:05, recovered by 15:12.",
    "metadata": {
      "service": "checkout-service",
      "environment": "production",
      "deploy_sha": "d9f3a1c",
      "on_call_engineer": "priya@example.com",
      "customer_impact": "~2400 failed transactions"
    },
    "sources_hint": ["log_bundle"]
  }'
```

Pass the returned `id` to `GET /api/analysis/{id}` to poll status.

---

## LLM Providers

| Provider | `LLM_PROVIDER` | Install extra |
|---|---|---|
| Anthropic (default) | `anthropic` | `.[anthropic]` |
| OpenAI | `openai` | `.[openai]` |
| Google Gemini | `google` | `.[google]` |
| AWS Bedrock | `bedrock` | `.[bedrock]` |

Switch providers by changing `LLM_PROVIDER` and `LLM_MODEL` in `.env` — no code changes required.

---

## Development

```bash
# Lint
ruff check src/
ruff format src/

# Tests
pytest
pytest tests/unit/
pytest --cov=src --cov-report=term

# DB migration
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Project Layout

```
src/
  agents/          # LangGraph nodes: orchestrator, log/code/defect analysts, synthesizer, chat
  adapters/        # Pluggable data sources (log bundle, code changes, defect DB) and incident systems
  api/             # FastAPI routes + Celery worker
  core/            # Config, DB, LLM factory, token tracker
  models/          # SQLAlchemy ORM + Pydantic schemas
  outputs/         # PDF (WeasyPrint) and PPTX (python-pptx) exporters
ui/src/            # React + Vite frontend
demo/              # Synthetic data for demo runs (logs, git diff, known defects)
docs/              # Design documentation
  PROMPTS.md       # System prompt design for every agent — rationale, format, tuning notes
tests/unit/        # Pytest unit tests (17 tests: routing, synthesizer, defect adapter)
```

---

## Configuration

Runtime behaviour is controlled by `config.yaml` (data sources, LLM params, retry thresholds, notification channels). See inline comments in that file.

For agent prompt design and tuning guidance, see [`docs/PROMPTS.md`](docs/PROMPTS.md).

---

## Phase Status

| Phase | Status |
|---|---|
| 1 — Core scaffold, models, API, React UI | ✅ Complete |
| 2 — All three analysis agents, adapters, exports | ✅ Complete |
| 3 — Workaround approval gate, notification adapters | 🔜 Planned |
| 4 — Evaluator agent, load testing, cloud deploy | 🔜 Planned |
