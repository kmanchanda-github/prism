"""Unit tests for the synthesizer agent."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.synthesizer import run_synthesis
from src.models.report import SubReport


def _make_state(sub_reports=None, confidence_score=0.0, context=None):
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
    state.context = context if context is not None else {}
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


# ---------------------------------------------------------------------------
# Feedback loop — improvement hints from state.context reach the LLM prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_synthesis_injects_improvement_hints_into_prompt():
    """This is the actual proof the feedback loop is real, not decorative:
    a hint placed in state.context (by worker.py, looked up from a prior
    evaluation) must appear in the HumanMessage actually sent to the LLM."""
    payload = {
        "root_cause": "x", "workaround": "y",
        "recommended_actions": [], "confidence_score": 0.8,
    }
    hint = "Ensure configuration changes affecting resource limits are peer-reviewed."
    state = _make_state(context={"improvement_hints": [hint]})

    with patch("src.agents.synthesizer.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(json.dumps(payload)))
        mock_llm_fn.return_value = mock_llm

        await run_synthesis(state)

    sent_messages = mock_llm.ainvoke.call_args[0][0]
    human_content = sent_messages[1].content
    assert hint in human_content
    assert "previously evaluated incidents" in human_content


@pytest.mark.asyncio
async def test_run_synthesis_omits_hints_section_when_none_available():
    payload = {
        "root_cause": "x", "workaround": "y",
        "recommended_actions": [], "confidence_score": 0.8,
    }
    state = _make_state(context={"improvement_hints": []})

    with patch("src.agents.synthesizer.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(json.dumps(payload)))
        mock_llm_fn.return_value = mock_llm

        await run_synthesis(state)

    sent_messages = mock_llm.ainvoke.call_args[0][0]
    human_content = sent_messages[1].content
    assert "previously evaluated incidents" not in human_content
