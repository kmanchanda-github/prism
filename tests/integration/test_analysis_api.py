"""Integration tests for the /api/analysis routes.

Exercises the real FastAPI app, routing, Pydantic validation, and SQLAlchemy
ORM against an isolated SQLite database — only the Celery dispatch (no broker
in CI) is stubbed out.
"""
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.main import app
from src.core.database import Base, get_db


@pytest.fixture
async def client(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    import src.api.worker as worker
    monkeypatch.setattr(worker.run_analysis_task, "delay", MagicMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


def _incident_payload(**overrides):
    payload = {
        "title": "Checkout service timeout spike",
        "description": "504s on ~40% of payment requests",
        "severity": "P1",
        "metadata": {"service": "checkout-service"},
        "sources_hint": ["log_bundle"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_submit_analysis_creates_pending_report(client):
    resp = await client.post("/api/analysis", json=_incident_payload())

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["current_version"] == 0
    assert "id" in body


@pytest.mark.asyncio
async def test_submit_analysis_dispatches_celery_task(client, monkeypatch):
    import src.api.worker as worker

    resp = await client.post("/api/analysis", json=_incident_payload())
    assert resp.status_code == 202

    worker.run_analysis_task.delay.assert_called_once()
    _, kwargs = worker.run_analysis_task.delay.call_args
    assert kwargs["incident_dict"]["title"] == "Checkout service timeout spike"


@pytest.mark.asyncio
async def test_get_analysis_returns_report_without_version_while_pending(client):
    submit = await client.post("/api/analysis", json=_incident_payload())
    analysis_id = submit.json()["id"]

    resp = await client.get(f"/api/analysis/{analysis_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["id"] == analysis_id
    assert body["report"]["status"] == "pending"
    assert body["version"] is None


@pytest.mark.asyncio
async def test_get_analysis_404_for_unknown_id(client):
    resp = await client.get("/api/analysis/does-not-exist")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_analysis_rejects_invalid_severity(client):
    resp = await client.post("/api/analysis", json=_incident_payload(severity="P9"))

    assert resp.status_code == 422
