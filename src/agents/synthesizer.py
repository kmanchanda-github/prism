import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.core.llm import get_llm

_SYSTEM = """You are a senior site reliability engineer synthesizing findings from multiple analysis agents.

Given sub-agent findings, produce a JSON object with exactly these keys:
{
  "root_cause": "...",
  "workaround": "...",
  "recommended_actions": [
    {"id": "1", "title": "...", "description": "...", "priority": "high|medium|low",
     "type": "defect_fix|product_improvement|process|monitoring", "owner": null, "due_date": null}
  ],
  "confidence_score": 0.0
}

confidence_score: 0.0-1.0 reflecting how certain you are of the root cause.
Be concrete and actionable. Do not hedge excessively."""


async def run_synthesis(state) -> dict:
    llm = get_llm()

    findings_text = "\n\n".join(
        f"=== {r.agent} (confidence: {r.confidence:.0%}) ===\n{r.findings}"
        for r in state.sub_reports
    )

    response = await llm.ainvoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=(
            f"Incident: {state.incident.title}\n"
            f"Severity: {state.incident.severity}\n"
            f"Description: {state.incident.description}\n\n"
            f"Sub-agent findings:\n{findings_text}"
        )),
    ])

    state.token_tracker.record(
        "synthesizer",
        response.usage_metadata.get("input_tokens", 0),
        response.usage_metadata.get("output_tokens", 0),
    )

    match = re.search(r"\{.*\}", response.content, re.DOTALL)
    if not match:
        return {
            "root_cause": response.content,
            "workaround": "",
            "recommended_actions": [],
            "confidence_score": 0.3,
        }

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "root_cause": response.content,
            "workaround": "",
            "recommended_actions": [],
            "confidence_score": 0.3,
        }

    return {
        "root_cause": data.get("root_cause", ""),
        "workaround": data.get("workaround", ""),
        "recommended_actions": data.get("recommended_actions", []),
        "confidence_score": float(data.get("confidence_score", 0.5)),
    }
