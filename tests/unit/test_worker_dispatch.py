"""Regression test for eager-mode task dispatch (single-container deployments)."""
import asyncio

import pytest

from src.api.worker import run_analysis_task


@pytest.mark.asyncio
async def test_run_analysis_task_schedules_on_running_loop_in_eager_mode(monkeypatch):
    """Single-container deployments (e.g. Hugging Face Spaces) set
    CELERY_BROKER_URL=memory://, which enables task_always_eager — meaning
    run_analysis_task executes directly on the caller's thread instead of a
    separate worker process. Since that caller is FastAPI's already-running
    event loop, asyncio.run() would raise RuntimeError; this confirms the
    task instead schedules _run() on the existing loop and returns without
    blocking."""
    called = {}

    async def fake_run(task, analysis_id, incident_dict, context, notify_channels):
        called["analysis_id"] = analysis_id

    monkeypatch.setattr("src.api.worker._run", fake_run)

    # Invoke the task's underlying function directly (bypassing Celery's
    # message dispatch) from within this test's already-running event loop —
    # the same situation eager mode puts it in.
    run_analysis_task.run(
        analysis_id="test-id", incident_dict={}, context={}, notify_channels=[]
    )

    await asyncio.sleep(0)  # let the scheduled task run one tick
    assert called.get("analysis_id") == "test-id"
