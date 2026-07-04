"""Unit tests for the synthesizer agent."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.synthesizer import run_synthesis
from src.models.report import SubReport


def _make_state(sub_reports=None, confidence_score=0.0):
    from src.models.incident import Incident
    incident = Incident(
        id="test-001",
        title="Pool exhaustion",
        description="504s on checkout",
        severity="P1",
        metadata={},
    )
    token_tracker = MagicMock()
    token_tracker.record = MagicMock()

    state = MagicMock()
    state.incident = incident
    state.sub_reports = sub_reports or []
    state.confidence_score = confidence_score
    state.token_tracker = token_tracker
    return state


def _llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    msg.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    return msg


# ---------------------------------------------------------------------------
# Happy path — valid JSON from LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_synthesis_parses_valid_json():
    payload = {
        "root_cause": "DB pool reduced from 20 to 5",
        "workaround": "Roll back pool config",
        "recommended_actions": [
            {"id": "1", "title": "Restore pool size", "description": "Set pool_size=20",
             "priority": "high", "type": "defect_fix", "owner": None, "due_date": None}
        ],
        "confidence_score": 0.9,
    }
    state = _make_state(sub_reports=[
        SubReport(agent="log_agent", findings="timeouts at 14:32", sources_used=[], confidence=0.7),
    ])

    with patch("src.agents.synthesizer.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(json.dumps(payload)))
        mock_llm_fn.return_value = mock_llm

        result = await run_synthesis(state)

    assert result["root_cause"] == "DB pool reduced from 20 to 5"
    assert result["workaround"] == "Roll back pool config"
    assert len(result["recommended_actions"]) == 1
    assert result["confidence_score"] == 0.9


# ---------------------------------------------------------------------------
# Graceful fallback — LLM returns prose without JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_synthesis_falls_back_on_no_json():
    state = _make_state(sub_reports=[
        SubReport(agent="log_agent", findings="some findings", sources_used=[], confidence=0.5),
    ])

    with patch("src.agents.synthesizer.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response("Unable to determine root cause."))
        mock_llm_fn.return_value = mock_llm

        result = await run_synthesis(state)

    assert result["root_cause"] == "Unable to determine root cause."
    assert result["recommended_actions"] == []
    assert result["confidence_score"] == 0.3


# ---------------------------------------------------------------------------
# Graceful fallback — braces matched by regex but content isn't valid JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_synthesis_falls_back_on_malformed_json():
    state = _make_state(sub_reports=[
        SubReport(agent="log_agent", findings="some findings", sources_used=[], confidence=0.5),
    ])
    malformed = 'Root cause: {"root_cause": "pool exhaustion", "workaround": }'

    with patch("src.agents.synthesizer.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(malformed))
        mock_llm_fn.return_value = mock_llm

        result = await run_synthesis(state)

    assert result["root_cause"] == malformed
    assert result["recommended_actions"] == []
    assert result["confidence_score"] == 0.3


# ---------------------------------------------------------------------------
# Confidence score is cast to float even if LLM returns string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_synthesis_coerces_confidence_to_float():
    payload = {
        "root_cause": "x",
        "workaround": "y",
        "recommended_actions": [],
        "confidence_score": "0.75",
    }
    state = _make_state()

    with patch("src.agents.synthesizer.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(json.dumps(payload)))
        mock_llm_fn.return_value = mock_llm

        result = await run_synthesis(state)

    assert isinstance(result["confidence_score"], float)
    assert result["confidence_score"] == 0.75
