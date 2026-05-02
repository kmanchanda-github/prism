from datetime import datetime
from typing import Literal

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class IncidentORM(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, default="manual")
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sources_hint: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Pydantic schemas (API in/out)
# ---------------------------------------------------------------------------
from pydantic import BaseModel, Field
import uuid


class IncidentCreate(BaseModel):
    title: str
    description: str
    severity: Literal["P0", "P1", "P2", "P3"]
    metadata: dict = Field(default_factory=dict)
    sources_hint: list[str] | None = None
    notify_channels: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["manual", "jira", "salesforce", "generic"] = "manual"
    title: str
    description: str
    severity: Literal["P0", "P1", "P2", "P3"]
    metadata: dict = Field(default_factory=dict)
    sources_hint: list[str] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}
