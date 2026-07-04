"""Shared helper for extracting the LLM-stated confidence score from agent prose output."""
import re

_CONFIDENCE_RE = re.compile(r"confidence(?:\s+score)?\s*:?\s*\**\s*(-?\d*\.?\d+)", re.IGNORECASE)


def parse_confidence(text: str, default: float = 0.5) -> float:
    """Extract a 0.0-1.0 confidence score from free-form LLM prose.

    Agents are prompted to end their response with a line like
    "Confidence: 0.75". Takes the last match (the concluding statement,
    not an earlier passing mention of "confidence") and clamps to [0, 1].
    Falls back to `default` if no parseable score is found.
    """
    matches = _CONFIDENCE_RE.findall(text)
    if not matches:
        return default
    try:
        value = float(matches[-1])
    except ValueError:
        return default
    return max(0.0, min(1.0, value))
