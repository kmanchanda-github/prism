"""Unit tests for DefectDbAdapter matching and scoring logic."""
import json
import tempfile
from pathlib import Path

import pytest

from src.adapters.data_sources.defect_db import DefectDbAdapter
from src.models.incident import Incident

_SAMPLE_DEFECTS = [
    {
        "id": "DEFECT-1041",
        "title": "HikariCP pool exhaustion under concurrent lock contention",
        "service": "checkout-service",
        "status": "known",
        "severity": "P1",
        "component": "database / connection pool",
        "tags": ["db-pool", "hikari", "connection-timeout", "lock-contention"],
        "description": "Pool too small causes timeout.",
        "root_cause": "pool_size too small",
        "workaround": "Set pool_size >= 20",
        "resolution": "Hard minimum in config",
        "first_seen": "2024-11-12",
        "last_seen": "2025-05-30",
        "occurrences": 3,
        "related_prs": [],
        "post_mortems": [],
    },
    {
        "id": "DEFECT-0744",
        "title": "Redis cache miss storm on restart",
        "service": "checkout-service",
        "status": "resolved",
        "severity": "P2",
        "component": "cart cache",
        "tags": ["redis", "cache", "restart"],
        "description": "Cold start cache miss.",
        "root_cause": "no cache warm-up",
        "workaround": "Rolling restarts",
        "resolution": "Cache pre-warming",
        "first_seen": "2024-10-22",
        "last_seen": "2024-10-22",
        "occurrences": 1,
        "related_prs": [],
        "post_mortems": [],
    },
]


def _incident(**kwargs) -> Incident:
    defaults = dict(
        id="test-001",
        title="Checkout service timeout spike",
        description="DB connection pool exhausted causing 504s",
        severity="P1",
        metadata={"service": "checkout-service"},
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def _write_db(defects: list) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump(defects, tmp)
    tmp.flush()
    return Path(tmp.name)


@pytest.mark.asyncio
async def test_fetch_returns_chunks_from_file():
    db_path = _write_db(_SAMPLE_DEFECTS)
    adapter = DefectDbAdapter()
    incident = _incident()
    chunks = await adapter.fetch(incident, {"defect_db_path": str(db_path)})
    assert len(chunks) == 1
    assert "DEFECT-1041" in chunks[0].content


@pytest.mark.asyncio
async def test_fetch_scores_service_match_higher():
    db_path = _write_db(_SAMPLE_DEFECTS)
    adapter = DefectDbAdapter()
    incident = _incident(
        description="pool exhausted connection timeout",
        metadata={"service": "checkout-service"},
    )
    chunks = await adapter.fetch(incident, {"defect_db_path": str(db_path)})
    content = chunks[0].content
    # DEFECT-1041 should appear before DEFECT-0744 (higher relevance score)
    assert content.index("DEFECT-1041") < content.index("DEFECT-0744")


@pytest.mark.asyncio
async def test_fetch_returns_empty_when_file_missing():
    adapter = DefectDbAdapter()
    chunks = await adapter.fetch(_incident(), {"defect_db_path": "/nonexistent/path.json"})
    assert chunks == []


@pytest.mark.asyncio
async def test_fetch_falls_back_to_all_when_no_matches():
    unrelated_defects = [
        {**_SAMPLE_DEFECTS[0], "service": "payments-service", "tags": ["unrelated"]},
        {**_SAMPLE_DEFECTS[1], "service": "payments-service", "tags": ["unrelated"]},
    ]
    db_path = _write_db(unrelated_defects)
    adapter = DefectDbAdapter()
    incident = _incident(
        title="Completely unrelated issue",
        description="Something that matches nothing",
        metadata={"service": "unknown-service"},
    )
    chunks = await adapter.fetch(incident, {"defect_db_path": str(db_path)})
    # Falls back to returning all defects
    assert len(chunks) == 1
    parsed = json.loads(chunks[0].content)
    assert len(parsed) == 2
