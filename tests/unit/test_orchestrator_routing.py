"""Unit tests for orchestrator routing and graph assembly."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.orchestrator import (
    AnalysisState,
    build_graph,
    fan_out,
    should_retry,
)
from src.models.incident import Incident
from src.models.report import SubReport


def _make_incident(**kwargs) -> Incident:
    defaults = dict(
        id="test-incident-001",
        title="DB connection pool exhaustion",
        description="Checkout service returning 504s",
        severity="P1",
        metadata={"service": "checkout-service", "deploy_sha": "d9f3a1c"},
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def _make_state(**kwargs) -> AnalysisState:
    defaults = dict(incident=_make_incident())
    defaults.update(kwargs)
    return AnalysisState(**defaults)


# ---------------------------------------------------------------------------
# fan_out
# ---------------------------------------------------------------------------

def test_fan_out_sends_all_active_agents():
    state = _make_state(active_agents=["log_agent", "code_agent", "defect_agent"])
    sends = fan_out(state)
    destinations = [s.node for s in sends]
    assert destinations == ["log_agent", "code_agent", "defect_agent"]


def test_fan_out_empty_agents():
    state = _make_state(active_agents=[])
    assert fan_out(state) == []


def test_fan_out_single_agent():
    state = _make_state(active_agents=["log_agent"])
    sends = fan_out(state)
    assert len(sends) == 1
    assert sends[0].node == "log_agent"


# ---------------------------------------------------------------------------
# should_retry
# ---------------------------------------------------------------------------

def test_should_retry_below_threshold_and_retries_available():
    state = _make_state(confidence_score=0.4, retry_count=0)
    assert should_retry(state) == "route_decision"


def test_should_retry_above_threshold():
    state = _make_state(confidence_score=0.85, retry_count=0)
    assert should_retry(state) == "notify"


def test_should_retry_at_threshold():
    state = _make_state(confidence_score=0.7, retry_count=0)
    assert should_retry(state) == "notify"


def test_should_retry_max_retries_exhausted():
    state = _make_state(confidence_score=0.3, retry_count=2)
    assert should_retry(state) == "notify"


def test_should_retry_one_retry_remaining():
    state = _make_state(confidence_score=0.3, retry_count=1)
    assert should_retry(state) == "route_decision"


# ---------------------------------------------------------------------------
# AnalysisState sub_report accumulation
# ---------------------------------------------------------------------------

def test_sub_reports_accumulate_with_operator_add():
    """Annotated[list, operator.add] should merge parallel agent results."""
    import operator
    report_a = SubReport(agent="log_agent", findings="logs ok", sources_used=[], confidence=0.7)
    report_b = SubReport(agent="code_agent", findings="bad diff", sources_used=[], confidence=0.8)

    state = _make_state(sub_reports=[report_a])
    merged = operator.add(state.sub_reports, [report_b])
    assert len(merged) == 2
    assert merged[0].agent == "log_agent"
    assert merged[1].agent == "code_agent"


# ---------------------------------------------------------------------------
# build_graph smoke test
# ---------------------------------------------------------------------------

def test_build_graph_compiles_without_error():
    graph = build_graph()
    assert graph is not None


# ---------------------------------------------------------------------------
# Full graph run — regression test for the dict-vs-AnalysisState bug
# ---------------------------------------------------------------------------

def _llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    msg.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
    return msg


@pytest.mark.asyncio
async def test_full_graph_run_result_is_dict_and_rehydrates_to_analysis_state():
    """graph.ainvoke() returns a plain dict, not an AnalysisState instance —
    src/api/worker.py must rehydrate it via AnalysisState(**result) before
    using attribute access. This regression-tests that rehydration path end
    to end (log_agent's LogBundleAdapter is mocked to return no chunks, so
    it skips its own LLM call and only route_decision and the synthesizer
    call the mocked LLM)."""
    synth_payload = json.dumps({
        "root_cause": "DB pool reduced from 20 to 5",
        "workaround": "Roll back pool config",
        "recommended_actions": [],
        "confidence_score": 0.85,
    })
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(side_effect=[
        _llm_response('["log_agent"]'),
        _llm_response(synth_payload),
    ])

    incident = _make_incident()
    initial = AnalysisState(incident=incident)

    with patch("src.agents.orchestrator.get_llm", return_value=mock_llm), \
         patch("src.agents.synthesizer.get_llm", return_value=mock_llm), \
         patch("src.agents.log_analyst.LogBundleAdapter.fetch", new=AsyncMock(return_value=[])):
        graph = build_graph()
        raw_result = await graph.ainvoke(initial)

    assert isinstance(raw_result, dict)

    final = AnalysisState(**raw_result)
    assert final.root_cause == "DB pool reduced from 20 to 5"
    assert final.confidence_score == 0.85
    assert final.token_tracker is not None
