"""Integration tests for POST/GET /api/analysis/{id}/evaluate(-ion)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.main import app
from src.core.database import Base, get_db
from src.models.incident import IncidentORM
from src.models.report import AnalysisReportORM, AnalysisVersionORM


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

    # Seed a completed analysis directly, mirroring what worker._run() would
    # have produced, so we can evaluate it without a live LLM pipeline run.
    async with session_factory() as session:
        session.add(IncidentORM(
            id="inc-1", source="manual", title="Checkout timeout",
            description="504s on checkout", severity="P1",
            metadata_json={"service": "checkout-service"},
        ))
        session.add(AnalysisReportORM(id="an-1", incident_id="inc-1", status="complete", current_version=0))
        session.add(AnalysisVersionORM(
            analysis_id="an-1", incident_id="inc-1", version=0,
            root_cause="DB pool reduced from 20 to 5", workaround="Revert pool size",
            recommended_actions=[], sub_reports=[], confidence_score=0.9,
            edited_by="ai", edit_source="ai_generated",
        ))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


def _llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    msg.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    return msg


@pytest.mark.asyncio
async def test_evaluate_404s_for_unknown_analysis(client):
    resp = await client.post(
        "/api/analysis/does-not-exist/evaluate",
        json={"actual_resolution": "reverted the config"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_scores_and_persists_hint(client):
    eval_payload = {
        "accuracy_score": 0.95,
        "what_it_got_right": "Correctly identified the pool size change.",
        "what_it_missed": "",
        "hint_summary": "Peer-review pool size changes before deploy.",
    }

    with patch("src.agents.evaluator.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(json.dumps(eval_payload)))
        mock_llm_fn.return_value = mock_llm

        resp = await client.post(
            "/api/analysis/an-1/evaluate",
            json={"actual_resolution": "Reverted pool size, confirmed root cause."},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["accuracy_score"] == 0.95
    assert body["hint_summary"] == "Peer-review pool size changes before deploy."

    # GET should now return the persisted evaluation
    get_resp = await client.get("/api/analysis/an-1/evaluation")
    assert get_resp.status_code == 200
    assert get_resp.json()["hint_summary"] == "Peer-review pool size changes before deploy."


@pytest.mark.asyncio
async def test_get_evaluation_404s_when_none_exists(client):
    resp = await client.get("/api/analysis/an-1/evaluation")
    assert resp.status_code == 404
