from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ImprovementHintORM(Base):
    __tablename__ = "improvement_hints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String, index=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    service: Mapped[str] = mapped_column(String, index=True, default="")
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0)
    actual_resolution: Mapped[str] = mapped_column(String)
    what_it_got_right: Mapped[str] = mapped_column(String, default="")
    what_it_missed: Mapped[str] = mapped_column(String, default="")
    hint_summary: Mapped[str] = mapped_column(String)
    langsmith_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EvaluationRequest(BaseModel):
    actual_resolution: str


class EvaluationResult(BaseModel):
    analysis_id: str
    accuracy_score: float
    what_it_got_right: str
    what_it_missed: str
    hint_summary: str
    created_at: datetime

    model_config = {"from_attributes": True}
