import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.incident import Incident, IncidentCreate
from src.models.report import (
    AnalysisEditRequest,
    AnalysisReport,
    AnalysisReportORM,
    AnalysisVersion,
    AnalysisVersionORM,
)

router = APIRouter(tags=["analysis"])


@router.post("/analysis", response_model=AnalysisReport, status_code=202)
async def submit_analysis(
    incident: IncidentCreate,
    db: AsyncSession = Depends(get_db),
):
    from src.api.worker import run_analysis_task

    inc = Incident(
        source="manual",
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        metadata=incident.metadata,
        sources_hint=incident.sources_hint,
    )

    analysis_id = str(uuid.uuid4())
    report = AnalysisReportORM(id=analysis_id, incident_id=inc.id, status="pending")
    db.add(report)
    await db.commit()

    run_analysis_task.delay(
        analysis_id=analysis_id,
        incident_dict=inc.model_dump(mode="json"),
        context={},
        notify_channels=incident.notify_channels,
    )

    await db.refresh(report)
    return AnalysisReport.model_validate(report)


@router.get("/analysis/{analysis_id}", response_model=dict)
async def get_analysis(analysis_id: str, db: AsyncSession = Depends(get_db)):
    report = await db.get(AnalysisReportORM, analysis_id)
    if not report:
        raise HTTPException(status_code=404, detail="Analysis not found")

    version = None
    if report.status == "complete":
        result = await db.execute(
            select(AnalysisVersionORM)
            .where(AnalysisVersionORM.analysis_id == analysis_id)
            .where(AnalysisVersionORM.version == report.current_version)
        )
        version = result.scalar_one_or_none()

    return {
        "report": AnalysisReport.model_validate(report),
        "version": AnalysisVersion.model_validate(version) if version else None,
    }


@router.patch("/analysis/{analysis_id}", response_model=AnalysisVersion)
async def edit_analysis(
    analysis_id: str,
    edit: AnalysisEditRequest,
    editor_email: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(AnalysisReportORM, analysis_id)
    if not report:
        raise HTTPException(status_code=404, detail="Analysis not found")

    next_version = report.current_version + 1
    new_version = AnalysisVersionORM(
        analysis_id=analysis_id,
        incident_id=report.incident_id,
        version=next_version,
        root_cause=edit.root_cause,
        workaround=edit.workaround,
        recommended_actions=[a.model_dump() for a in edit.recommended_actions],
        sub_reports=[],
        confidence_score=1.0,  # engineer-approved
        edited_by=editor_email,
        edit_source=edit.edit_source,
    )
    db.add(new_version)
    report.current_version = next_version
    await db.commit()
    await db.refresh(new_version)
    return AnalysisVersion.model_validate(new_version)


@router.get("/analysis/{analysis_id}/versions", response_model=list[AnalysisVersion])
async def list_versions(analysis_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AnalysisVersionORM)
        .where(AnalysisVersionORM.analysis_id == analysis_id)
        .order_by(AnalysisVersionORM.version)
    )
    return [AnalysisVersion.model_validate(v) for v in result.scalars().all()]
