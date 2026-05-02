import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.chat import ChatMessage, ChatMessageORM, ChatRequest
from src.models.report import AnalysisReportORM, AnalysisVersionORM

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

    # Load current version
    current_version = None
    if report.status == "complete":
        result = await db.execute(
            select(AnalysisVersionORM)
            .where(AnalysisVersionORM.analysis_id == analysis_id)
            .where(AnalysisVersionORM.version == report.current_version)
        )
        current_version = result.scalar_one_or_none()

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

    from src.agents.chat_agent import stream_response

    full_response = ""
    suggested_edit = None

    async def generate():
        nonlocal full_response, suggested_edit
        async for token in stream_response(
            message=request.message,
            incident=None,        # TODO: load from DB in Phase 2
            sub_reports=[],
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
