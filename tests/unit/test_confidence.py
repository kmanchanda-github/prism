"""Unit tests for the shared LLM confidence-score parser."""
from src.agents.confidence import parse_confidence


def test_parse_confidence_extracts_trailing_statement():
    text = "Logs show a clear pool exhaustion pattern.\nConfidence: 0.85"
    assert parse_confidence(text) == 0.85


def test_parse_confidence_handles_confidence_score_label():
    text = "Root cause is likely the deploy.\nConfidence score: 0.6"
    assert parse_confidence(text) == 0.6


def test_parse_confidence_handles_bold_markdown():
    text = "Findings...\n**Confidence: 0.92**"
    assert parse_confidence(text) == 0.92


def test_parse_confidence_takes_last_match_when_mentioned_earlier():
    text = "I have high confidence this matters.\nConfidence: 0.4"
    assert parse_confidence(text) == 0.4


def test_parse_confidence_falls_back_to_default_when_absent():
    text = "Unable to determine anything conclusive from the provided data."
    assert parse_confidence(text) == 0.5
    assert parse_confidence(text, default=0.3) == 0.3


def test_parse_confidence_clamps_out_of_range_values():
    assert parse_confidence("Confidence: 1.4") == 1.0
    assert parse_confidence("Confidence: -0.2") == 0.0
