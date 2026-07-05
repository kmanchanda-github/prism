"""Unit tests for model-aware cost calculation in TokenTracker."""
from src.core.token_tracker import TokenTracker


def test_cost_uses_correct_rate_for_gpt4o():
    tracker = TokenTracker(model="gpt-4o")
    tracker.record("synthesizer", input_tokens=1_000_000, output_tokens=1_000_000)
    totals = tracker.totals()
    assert totals["estimated_cost_usd"] == 12.50  # $2.50 in + $10.00 out


def test_cost_uses_correct_rate_for_claude_sonnet():
    tracker = TokenTracker(model="claude-sonnet-4-6")
    tracker.record("synthesizer", input_tokens=1_000_000, output_tokens=1_000_000)
    totals = tracker.totals()
    assert totals["estimated_cost_usd"] == 18.00  # $3.00 in + $15.00 out


def test_unknown_model_falls_back_to_default_rate():
    tracker = TokenTracker(model="some-future-model-v9")
    tracker.record("synthesizer", input_tokens=1_000_000, output_tokens=1_000_000)
    totals = tracker.totals()
    assert totals["estimated_cost_usd"] == 12.50  # default fallback rate


def test_totals_aggregates_across_agents():
    tracker = TokenTracker(model="gpt-4o")
    tracker.record("log_agent", input_tokens=1000, output_tokens=200)
    tracker.record("code_agent", input_tokens=2000, output_tokens=400)
    totals = tracker.totals()
    assert totals["total_input"] == 3000
    assert totals["total_output"] == 600
    assert set(totals["per_agent"].keys()) == {"log_agent", "code_agent"}
    assert totals["model"] == "gpt-4o"


def test_defaults_to_settings_llm_model_when_not_specified(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(
        "src.core.config.get_settings",
        lambda: SimpleNamespace(llm_model="gpt-4o-mini"),
    )
    tracker = TokenTracker()
    assert tracker.model == "gpt-4o-mini"
