from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class Action(BaseModel):
    id: str
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    owner: str | None = None
    due_date: str | None = None
    type: Literal["defect_fix", "product_improvement", "process", "monitoring"]


class SubReport(BaseModel):
    agent: str
    findings: str
    sources_used: list[str]
    confidence: float


class AnalysisVersionORM(Base):
    __tablename__ = "analysis_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String, index=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    root_cause: Mapped[str] = mapped_column(String)
    workaround: Mapped[str] = mapped_column(String)
    recommended_actions: Mapped[list] = mapped_column(JSON, default=list)
    sub_reports: Mapped[list] = mapped_column(JSON, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    edited_by: Mapped[str] = mapped_column(String, default="ai")
    edit_source: Mapped[str] = mapped_column(String, default="ai_generated")
    applied_hints: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    langsmith_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisReportORM(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    rerun_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AnalysisVersion(BaseModel):
    analysis_id: str
    version: int
    root_cause: str
    workaround: str
    recommended_actions: list[Action]
    sub_reports: list[SubReport]
    confidence_score: float
    edited_by: str
    edit_source: Literal["ai_generated", "chat_suggestion", "manual_edit"]
    applied_hints: list[str] | None = None
    langsmith_run_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisReport(BaseModel):
    id: str
    incident_id: str
    status: Literal["pending", "running", "complete", "failed"]
    current_version: int
    token_usage: dict
    rerun_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisEditRequest(BaseModel):
    root_cause: str
    workaround: str
    recommended_actions: list[Action]
    edit_source: Literal["chat_suggestion", "manual_edit"] = "manual_edit"
