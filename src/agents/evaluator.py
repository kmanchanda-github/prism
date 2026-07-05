"""Evaluation & Improvement Agent — on-demand, post-closure.

Compares the AI's synthesized analysis against what actually happened, scores
accuracy, and produces a short hint for future similar incidents. The hint is
persisted (src/api/routes/evaluation.py) and looked up by service in the
orchestrator's fan_out step, so evaluated runs genuinely inform later ones —
see orchestrator.py::apply_improvement_hints.
"""
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.core.llm import get_llm

_SYSTEM = """You are a senior site reliability engineer conducting a post-incident review.

You will be given the AI-generated analysis produced during the incident (root cause,
workaround, recommended actions) and a description of what actually happened / how it
was really resolved. Compare them and produce a JSON object with exactly these keys:
{
  "accuracy_score": 0.0,
  "what_it_got_right": "...",
  "what_it_missed": "...",
  "hint_summary": "..."
}

accuracy_score: 0.0-1.0 reflecting how well the AI's root cause and workaround matched
what actually happened.
hint_summary: one concise, actionable sentence a future analysis on a similar incident
should keep in mind — specific enough to be useful, short enough to fit in a prompt.
Be honest and specific. Do not inflate the score to be polite."""


async def run_evaluation(
    *,
    incident_title: str,
    incident_description: str,
    root_cause: str,
    workaround: str,
    recommended_actions: list[dict],
    actual_resolution: str,
) -> dict:
    llm = get_llm()

    human = HumanMessage(content=(
        f"Incident: {incident_title}\n"
        f"Description: {incident_description}\n\n"
        f"AI-generated root cause: {root_cause}\n"
        f"AI-generated workaround: {workaround}\n"
        f"AI-generated recommended actions: {json.dumps(recommended_actions)}\n\n"
        f"What actually happened / how it was really resolved:\n{actual_resolution}"
    ))

    response = await llm.ainvoke([SystemMessage(content=_SYSTEM), human])

    match = re.search(r"\{.*\}", response.content, re.DOTALL)
    if not match:
        return {
            "accuracy_score": 0.5,
            "what_it_got_right": "",
            "what_it_missed": "",
            "hint_summary": response.content.strip()[:280],
        }

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "accuracy_score": 0.5,
            "what_it_got_right": "",
            "what_it_missed": "",
            "hint_summary": response.content.strip()[:280],
        }

    return {
        "accuracy_score": float(data.get("accuracy_score", 0.5)),
        "what_it_got_right": data.get("what_it_got_right", ""),
        "what_it_missed": data.get("what_it_missed", ""),
        "hint_summary": data.get("hint_summary", ""),
    }
