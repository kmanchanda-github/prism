"""Unit tests for the LangSmith feedback-attachment helper.

Must never break evaluation itself — no-ops cleanly when tracing isn't
configured or the run has no recorded trace ID.
"""
from unittest.mock import MagicMock, patch

from src.api.routes.evaluation import _attach_langsmith_feedback


def test_noop_when_no_run_id():
    with patch("langsmith.Client") as mock_client_cls:
        _attach_langsmith_feedback(None, 0.9, "some hint")
    mock_client_cls.assert_not_called()


def test_noop_when_langchain_api_key_not_set(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    with patch("langsmith.Client") as mock_client_cls:
        _attach_langsmith_feedback("run-123", 0.9, "some hint")
    mock_client_cls.assert_not_called()


def test_calls_create_feedback_when_configured(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_test_key")
    mock_client = MagicMock()
    with patch("langsmith.Client", return_value=mock_client):
        _attach_langsmith_feedback("run-123", 0.9, "some hint")
    mock_client.create_feedback.assert_called_once_with(
        run_id="run-123", key="accuracy", score=0.9, comment="some hint"
    )


def test_does_not_raise_if_langsmith_call_fails(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_test_key")
    with patch("langsmith.Client", side_effect=RuntimeError("network down")):
        _attach_langsmith_feedback("run-123", 0.9, "some hint")  # must not raise
