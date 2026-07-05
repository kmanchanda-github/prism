"""Unit tests for the evaluator agent."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.evaluator import run_evaluation


def _llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    msg.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    return msg


@pytest.mark.asyncio
async def test_run_evaluation_parses_valid_json():
    payload = {
        "accuracy_score": 0.9,
        "what_it_got_right": "Correctly identified the pool size reduction.",
        "what_it_missed": "Didn't flag the missing peer review step.",
        "hint_summary": "Check for config changes lacking peer review on pool settings.",
    }

    with patch("src.agents.evaluator.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response(json.dumps(payload)))
        mock_llm_fn.return_value = mock_llm

        result = await run_evaluation(
            incident_title="Checkout timeout",
            incident_description="504s on checkout",
            root_cause="Pool size reduced",
            workaround="Revert pool size",
            recommended_actions=[],
            actual_resolution="Reverted pool size, confirmed by on-call.",
        )

    assert result["accuracy_score"] == 0.9
    assert "pool size" in result["what_it_got_right"]
    assert "peer review" in result["hint_summary"]


@pytest.mark.asyncio
async def test_run_evaluation_falls_back_on_no_json():
    with patch("src.agents.evaluator.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response("Hard to say without more data."))
        mock_llm_fn.return_value = mock_llm

        result = await run_evaluation(
            incident_title="x", incident_description="y",
            root_cause="z", workaround="w", recommended_actions=[],
            actual_resolution="unclear",
        )

    assert result["accuracy_score"] == 0.5
    assert result["hint_summary"] == "Hard to say without more data."


@pytest.mark.asyncio
async def test_run_evaluation_falls_back_on_malformed_json():
    with patch("src.agents.evaluator.get_llm") as mock_llm_fn:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_llm_response('{"accuracy_score": }'))
        mock_llm_fn.return_value = mock_llm

        result = await run_evaluation(
            incident_title="x", incident_description="y",
            root_cause="z", workaround="w", recommended_actions=[],
            actual_resolution="unclear",
        )

    assert result["accuracy_score"] == 0.5
