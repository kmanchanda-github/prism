import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.chat import ChatMessage, ChatMessageORM, ChatRequest
from src.models.incident import Incident, IncidentORM
from src.models.report import AnalysisReportORM, AnalysisVersionORM

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/analysis/{analysis_id}/chat")
async def chat(
    analysis_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(AnalysisReportORM, analysis_id)
    if not report:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Load incident for full chat context
    incident_orm = await db.get(IncidentORM, report.incident_id)
    incident: Incident | None = None
    if incident_orm:
        incident = Incident(
            id=incident_orm.id,
            source=incident_orm.source,
            title=incident_orm.title,
            description=incident_orm.description,
            severity=incident_orm.severity,
            metadata=incident_orm.metadata_json or {},
            sources_hint=incident_orm.sources_hint,
            created_at=incident_orm.created_at,
        )

    # Load current version and its sub-reports
    current_version = None
    sub_reports = []
    if report.status == "complete":
        result = await db.execute(
            select(AnalysisVersionORM)
            .where(AnalysisVersionORM.analysis_id == analysis_id)
            .where(AnalysisVersionORM.version == report.current_version)
        )
        current_version = result.scalar_one_or_none()
        if current_version and current_version.sub_reports:
            from src.models.report import SubReport
            sub_reports = [SubReport(**r) for r in current_version.sub_reports]

    # Load conversation history
    hist_result = await db.execute(
        select(ChatMessageORM)
        .where(ChatMessageORM.analysis_id == analysis_id)
        .order_by(ChatMessageORM.id)
    )
    history = [ChatMessage.model_validate(m) for m in hist_result.scalars().all()]

    # Save user message
    user_msg = ChatMessageORM(
        analysis_id=analysis_id, role="user", content=request.message
    )
    db.add(user_msg)
    await db.commit()

    logger.info("chat request analysis_id=%s message_len=%d", analysis_id, len(request.message))

    from src.agents.chat_agent import stream_response

    full_response = ""
    suggested_edit = None

    async def generate():
        nonlocal full_response, suggested_edit
        async for token in stream_response(
            message=request.message,
            incident=incident,
            sub_reports=sub_reports,
            current_version=current_version,
            history=history,
        ):
            if token.startswith("\n__SUGGESTED_EDIT__"):
                suggested_edit = json.loads(token.replace("\n__SUGGESTED_EDIT__", ""))
            else:
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"

        # Save assistant message after streaming completes
        import asyncio
        asyncio.create_task(_save_assistant_message(analysis_id, full_response, suggested_edit, db))
        yield f"data: {json.dumps({'done': True, 'suggested_edit': suggested_edit})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/analysis/{analysis_id}/chat", response_model=list[ChatMessage])
async def get_chat_history(analysis_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessageORM)
        .where(ChatMessageORM.analysis_id == analysis_id)
        .order_by(ChatMessageORM.id)
    )
    return [ChatMessage.model_validate(m) for m in result.scalars().all()]


async def _save_assistant_message(analysis_id, content, suggested_edit, db):
    msg = ChatMessageORM(
        analysis_id=analysis_id,
        role="assistant",
        content=content,
        suggested_edit=suggested_edit,
    )
    db.add(msg)
    await db.commit()
