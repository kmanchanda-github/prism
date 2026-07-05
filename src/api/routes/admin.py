"""Demo-only tooling — not part of the product surface.

Seeds one fully-worked historical analysis (three versions, chat history,
token metrics) so a demo recording can show Version History and Chat depth
without waiting on a second live LLM run. Gated behind ENABLE_DEMO_SEED so
it's off by default; the HF Space and local dev enable it explicitly.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.database import get_db
from src.models.chat import ChatMessageORM
from src.models.incident import IncidentORM
from src.models.metrics import TokenMetricsORM
from src.models.report import AnalysisReportORM, AnalysisVersionORM

router = APIRouter(prefix="/admin", tags=["admin"])

DEMO_INCIDENT_ID = "demo-seed-incident-0001"
DEMO_ANALYSIS_ID = "demo-seed-analysis-0001"

_RECOMMENDED_ACTIONS = [
    {
        "id": "1", "title": "Revert connection pool size",
        "description": "Restore db_pool_size to 20 in application-production.properties.",
        "priority": "high", "type": "defect_fix", "owner": None, "due_date": None,
    },
    {
        "id": "2", "title": "Require review on pool-size changes",
        "description": "Add a peer-review gate specifically for connection pool and concurrency settings.",
        "priority": "medium", "type": "process", "owner": None, "due_date": None,
    },
]

_SUB_REPORTS = [
    {
        "agent": "log_agent",
        "findings": (
            "Error spike began at 09:14 UTC, immediately following the a821f3e deploy. "
            "504 errors with pool-wait-timeout signatures climbed from 0.1% to 31% of "
            "checkout requests within six minutes. Postgres logs show connection wait "
            "queuing starting at the same timestamp; nginx traffic volume stayed flat, "
            "ruling out a load spike.\n\nConfidence: 0.92"
        ),
        "sources_used": ["log_bundle:checkout-service.log:chunk0", "log_bundle:postgres.log:chunk0"],
        "confidence": 0.92,
    },
    {
        "agent": "code_agent",
        "findings": (
            "Deploy a821f3e reduced db_pool_size from 20 to 8 as part of a config cleanup "
            "unrelated to performance tuning — the commit message describes it as removing "
            "'unused headroom'. No load test was run against the new value under production "
            "concurrency.\n\nConfidence: 0.90"
        ),
        "sources_used": ["code_changes:a821f3e.diff"],
        "confidence": 0.90,
    },
    {
        "agent": "defect_agent",
        "findings": (
            "Matches DEFECT-1041 (HikariCP pool exhaustion under concurrent lock contention) "
            "— same failure signature as a previously known, unresolved issue on this service.\n\n"
            "Confidence: 0.85"
        ),
        "sources_used": ["defect_db:known_issues.json"],
        "confidence": 0.85,
    },
]

_ROOT_CAUSE_V0 = (
    "The database connection pool size was reduced from 20 to 8 during a routine "
    "configuration cleanup in deploy a821f3e, causing pool exhaustion under normal "
    "production load."
)
_ROOT_CAUSE_V1 = (
    "The database connection pool size was reduced from 20 to 8 in deploy a821f3e "
    "during what was intended as a routine configuration cleanup — the change was not "
    "flagged as risky because it wasn't reviewed against production concurrency "
    "requirements."
)
_ROOT_CAUSE_V2 = (
    "The database connection pool size was reduced from 20 to 8 in deploy a821f3e "
    "during a configuration cleanup. This was a pool-sizing issue, not a payment "
    "gateway problem — gateway latency stayed flat throughout the incident window "
    "while pool-wait-time errors climbed immediately after the deploy."
)
_WORKAROUND = (
    "Revert the connection pool size to 20 and redeploy. Longer term: require review "
    "on connection-pool changes specifically."
)
_APPLIED_HINTS = [
    "Load-test connection pool size changes against realistic concurrency before "
    "rolling out to production.",
]


@router.post("/seed-demo")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    """Idempotent — safe to call before every take. Returns the seeded analysis ID."""
    if not get_settings().enable_demo_seed:
        raise HTTPException(status_code=404, detail="Not found")

    for stmt in (
        delete(ChatMessageORM).where(ChatMessageORM.analysis_id == DEMO_ANALYSIS_ID),
        delete(AnalysisVersionORM).where(AnalysisVersionORM.analysis_id == DEMO_ANALYSIS_ID),
        delete(TokenMetricsORM).where(TokenMetricsORM.analysis_id == DEMO_ANALYSIS_ID),
        delete(AnalysisReportORM).where(AnalysisReportORM.id == DEMO_ANALYSIS_ID),
        delete(IncidentORM).where(IncidentORM.id == DEMO_INCIDENT_ID),
    ):
        await db.execute(stmt)
    await db.commit()

    now = datetime.utcnow()

    db.add(IncidentORM(
        id=DEMO_INCIDENT_ID,
        source="manual",
        title="Checkout service timeout spike — payment failures (prior incident)",
        description=(
            "Similar checkout timeout spike two weeks earlier — DB connection pool "
            "reduced during a routine config cleanup."
        ),
        severity="P1",
        metadata_json={
            "service": "checkout-service",
            "environment": "production",
            "deploy_sha": "a821f3e",
            "on_call_engineer": "priya@example.com",
        },
        sources_hint=["log_bundle"],
        created_at=now - timedelta(days=14, minutes=35),
    ))

    db.add(AnalysisReportORM(
        id=DEMO_ANALYSIS_ID,
        incident_id=DEMO_INCIDENT_ID,
        status="complete",
        current_version=2,
        token_usage={
            "total_input": 12500, "total_output": 1850,
            "total_tokens": 14350, "estimated_cost_usd": 0.0621,
        },
        rerun_count=0,
        created_at=now - timedelta(days=14, minutes=35),
        updated_at=now - timedelta(days=14, minutes=10),
    ))

    db.add(AnalysisVersionORM(
        analysis_id=DEMO_ANALYSIS_ID, incident_id=DEMO_INCIDENT_ID, version=0,
        root_cause=_ROOT_CAUSE_V0, workaround=_WORKAROUND,
        recommended_actions=_RECOMMENDED_ACTIONS, sub_reports=_SUB_REPORTS,
        confidence_score=0.9, edited_by="ai", edit_source="ai_generated",
        applied_hints=_APPLIED_HINTS,
        created_at=now - timedelta(days=14, minutes=30),
    ))
    db.add(AnalysisVersionORM(
        analysis_id=DEMO_ANALYSIS_ID, incident_id=DEMO_INCIDENT_ID, version=1,
        root_cause=_ROOT_CAUSE_V1, workaround=_WORKAROUND,
        recommended_actions=_RECOMMENDED_ACTIONS, sub_reports=_SUB_REPORTS,
        confidence_score=1.0, edited_by="priya@example.com", edit_source="manual_edit",
        applied_hints=_APPLIED_HINTS,
        created_at=now - timedelta(days=14, minutes=18),
    ))
    db.add(AnalysisVersionORM(
        analysis_id=DEMO_ANALYSIS_ID, incident_id=DEMO_INCIDENT_ID, version=2,
        root_cause=_ROOT_CAUSE_V2, workaround=_WORKAROUND,
        recommended_actions=_RECOMMENDED_ACTIONS, sub_reports=_SUB_REPORTS,
        confidence_score=1.0, edited_by="ai", edit_source="chat_suggestion",
        applied_hints=_APPLIED_HINTS,
        created_at=now - timedelta(days=14, minutes=10),
    ))

    db.add(TokenMetricsORM(
        analysis_id=DEMO_ANALYSIS_ID, incident_id=DEMO_INCIDENT_ID,
        per_agent={
            "orchestrator": {"input": 200, "output": 15, "cost_usd": 0.0008},
            "log_agent": {"input": 5200, "output": 480, "cost_usd": 0.021},
            "code_agent": {"input": 3100, "output": 410, "cost_usd": 0.0145},
            "defect_agent": {"input": 1900, "output": 390, "cost_usd": 0.0092},
            "synthesizer": {"input": 2100, "output": 555, "cost_usd": 0.0146},
        },
        total_input=12500, total_output=1850, total_tokens=14350,
        estimated_cost_usd=0.0621,
        recorded_at=now - timedelta(days=14, minutes=30),
    ))

    db.add(ChatMessageORM(
        analysis_id=DEMO_ANALYSIS_ID, role="user",
        content=(
            "Why do you think the pool size change caused this instead of something "
            "on the payment gateway side?"
        ),
        created_at=now - timedelta(days=14, minutes=12),
    ))
    db.add(ChatMessageORM(
        analysis_id=DEMO_ANALYSIS_ID, role="assistant",
        content=(
            "Good question to rule out. Payment gateway p99 latency stayed flat across "
            "the whole incident window in the log bundle — the errors were 504s from "
            "connection-pool wait timeouts, not gateway response times. That points "
            "specifically at the pool-size reduction in deploy a821f3e, not the gateway "
            "integration."
        ),
        suggested_edit={"field": "root_cause", "value": _ROOT_CAUSE_V2},
        created_at=now - timedelta(days=14, minutes=11),
    ))

    await db.commit()

    return {
        "status": "seeded",
        "analysis_id": DEMO_ANALYSIS_ID,
        "url_path": f"/analysis/{DEMO_ANALYSIS_ID}",
    }
