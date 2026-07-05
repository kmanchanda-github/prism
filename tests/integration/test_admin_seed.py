"""Integration tests for the demo-only seed endpoint."""
from types import SimpleNamespace
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


@pytest.mark.asyncio
async def test_seed_demo_404s_when_disabled(client, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.admin.get_settings",
        lambda: SimpleNamespace(enable_demo_seed=False),
    )
    resp = await client.post("/admin/seed-demo")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_seed_demo_creates_full_analysis_when_enabled(client, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.admin.get_settings",
        lambda: SimpleNamespace(enable_demo_seed=True),
    )

    resp = await client.post("/admin/seed-demo")
    assert resp.status_code == 200
    analysis_id = resp.json()["analysis_id"]

    report = await client.get(f"/api/analysis/{analysis_id}")
    assert report.status_code == 200
    body = report.json()
    assert body["report"]["status"] == "complete"
    assert body["version"]["version"] == 2
    assert body["version"]["edit_source"] == "chat_suggestion"
    assert body["version"]["applied_hints"], "seed data should demo the lessons-applied UI"

    versions = await client.get(f"/api/analysis/{analysis_id}/versions")
    assert len(versions.json()) == 3

    chat_history = await client.get(f"/api/analysis/{analysis_id}/chat")
    assert len(chat_history.json()) == 2


@pytest.mark.asyncio
async def test_seed_demo_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.admin.get_settings",
        lambda: SimpleNamespace(enable_demo_seed=True),
    )

    first = await client.post("/admin/seed-demo")
    second = await client.post("/admin/seed-demo")
    assert first.json()["analysis_id"] == second.json()["analysis_id"]

    versions = await client.get(f"/api/analysis/{second.json()['analysis_id']}/versions")
    assert len(versions.json()) == 3  # not doubled up
