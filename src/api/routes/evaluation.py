import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.evaluation import EvaluationRequest, EvaluationResult, ImprovementHintORM
from src.models.incident import IncidentORM
from src.models.report import AnalysisReportORM, AnalysisVersionORM

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evaluation"])


def _attach_langsmith_feedback(run_id: str | None, score: float, comment: str) -> None:
    """Attach the evaluation result as feedback on the synthesizer's original
    LangSmith trace. A no-op if tracing isn't configured or the run wasn't
    traced — evaluation itself must never fail because of this."""
    if not run_id or not os.environ.get("LANGCHAIN_API_KEY"):
        return
    try:
        from langsmith import Client
        Client().create_feedback(run_id=run_id, key="accuracy", score=score, comment=comment)
    except Exception:
        logger.exception("Failed to attach LangSmith feedback for run_id=%s", run_id)


@router.post("/analysis/{analysis_id}/evaluate", response_model=EvaluationResult)
async def evaluate_analysis(
    analysis_id: str,
    request: EvaluationRequest,
    db: AsyncSession = Depends(get_db),
):
    from src.agents.evaluator import run_evaluation

    report = await db.get(AnalysisReportORM, analysis_id)
    if not report:
        raise HTTPException(status_code=404, detail="Analysis not found")

    incident = await db.get(IncidentORM, report.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    version_result = await db.execute(
        select(AnalysisVersionORM)
        .where(AnalysisVersionORM.analysis_id == analysis_id)
        .where(AnalysisVersionORM.version == report.current_version)
    )
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=400, detail="Analysis has no completed version to evaluate")

    result = await run_evaluation(
        incident_title=incident.title,
        incident_description=incident.description,
        root_cause=version.root_cause,
        workaround=version.workaround,
        recommended_actions=version.recommended_actions,
        actual_resolution=request.actual_resolution,
    )

    hint = ImprovementHintORM(
        analysis_id=analysis_id,
        incident_id=incident.id,
        service=(incident.metadata_json or {}).get("service", ""),
        accuracy_score=result["accuracy_score"],
        actual_resolution=request.actual_resolution,
        what_it_got_right=result["what_it_got_right"],
        what_it_missed=result["what_it_missed"],
        hint_summary=result["hint_summary"],
    )
    db.add(hint)
    await db.commit()
    await db.refresh(hint)

    _attach_langsmith_feedback(version.langsmith_run_id, result["accuracy_score"], result["hint_summary"])

    return EvaluationResult(
        analysis_id=analysis_id,
        accuracy_score=result["accuracy_score"],
        what_it_got_right=result["what_it_got_right"],
        what_it_missed=result["what_it_missed"],
        hint_summary=result["hint_summary"],
        created_at=hint.created_at,
    )


@router.get("/analysis/{analysis_id}/evaluation", response_model=EvaluationResult)
async def get_evaluation(analysis_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ImprovementHintORM)
        .where(ImprovementHintORM.analysis_id == analysis_id)
        .order_by(ImprovementHintORM.created_at.desc())
    )
    hint = result.scalars().first()
    if not hint:
        raise HTTPException(status_code=404, detail="No evaluation found for this analysis")

    return EvaluationResult(
        analysis_id=hint.analysis_id,
        accuracy_score=hint.accuracy_score,
        what_it_got_right=hint.what_it_got_right,
        what_it_missed=hint.what_it_missed,
        hint_summary=hint.hint_summary,
        created_at=hint.created_at,
    )
