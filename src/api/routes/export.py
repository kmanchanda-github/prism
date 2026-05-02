from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.report import AnalysisReportORM, AnalysisVersionORM

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    format: Literal["pdf", "pptx"]
    template: Literal["technical", "executive", "customer"] = "technical"


@router.post("/analysis/{analysis_id}/export")
async def export_analysis(
    analysis_id: str,
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(AnalysisReportORM, analysis_id)
    if not report or report.status != "complete":
        raise HTTPException(status_code=404, detail="Completed analysis not found")

    result = await db.execute(
        select(AnalysisVersionORM)
        .where(AnalysisVersionORM.analysis_id == analysis_id)
        .where(AnalysisVersionORM.version == report.current_version)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Analysis version not found")

    exporter_key = f"{request.format}_{request.template}"
    exporters = {
        "pdf_technical": _pdf_technical,
        "pdf_executive": _pdf_executive,
        "pptx_executive": _pptx_executive,
        "pptx_customer": _pptx_customer,
    }

    exporter = exporters.get(exporter_key)
    if not exporter:
        raise HTTPException(status_code=400, detail=f"Unsupported combination: {exporter_key}")

    file_path = await exporter(analysis_id, version)
    filename = f"analysis_{analysis_id[:8]}_{request.template}.{request.format}"
    return FileResponse(path=file_path, filename=filename)


async def _pdf_technical(analysis_id: str, version) -> str:
    from src.outputs.exporters.pdf_technical import generate
    return await generate(analysis_id, version)


async def _pdf_executive(analysis_id: str, version) -> str:
    from src.outputs.exporters.pdf_executive import generate
    return await generate(analysis_id, version)


async def _pptx_executive(analysis_id: str, version) -> str:
    from src.outputs.exporters.pptx_executive import generate
    return await generate(analysis_id, version)


async def _pptx_customer(analysis_id: str, version) -> str:
    from src.outputs.exporters.pptx_customer import generate
    return await generate(analysis_id, version)
