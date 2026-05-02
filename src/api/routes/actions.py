from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.metrics import ActionAuditORM
from src.models.report import AnalysisReportORM

router = APIRouter(tags=["actions"])


class ActionRequest(BaseModel):
    action_type: Literal["execute_workaround", "notify_slack", "notify_email", "notify_webex", "share"]
    performed_by: str = "anonymous"
    payload: dict = {}


@router.post("/analysis/{analysis_id}/action")
async def execute_action(
    analysis_id: str,
    request: ActionRequest,
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(AnalysisReportORM, analysis_id)
    if not report:
        raise HTTPException(status_code=404, detail="Analysis not found")

    audit = ActionAuditORM(
        analysis_id=analysis_id,
        action_type=request.action_type,
        performed_by=request.performed_by,
        payload=request.payload,
    )

    result_msg = "ok"

    if request.action_type == "execute_workaround":
        # Phase 3: LangGraph interrupt-based approval gate
        result_msg = "Workaround execution requires Phase 3 implementation."

    elif request.action_type in ("notify_slack", "notify_email", "notify_webex"):
        # Phase 3: trigger notification adapters
        result_msg = "Notification adapters available in Phase 3."

    audit.result = result_msg
    db.add(audit)
    await db.commit()

    return {"status": "recorded", "result": result_msg}
