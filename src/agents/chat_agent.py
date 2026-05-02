"""
Context-aware chat agent for engineer clarifications on a specific analysis.
Accepts full incident + sub-agent findings + current report + history as context.
Optionally returns a suggested_edit alongside prose.
"""
import json
import re
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.core.llm import get_llm
from src.models.chat import ChatMessage

_SYSTEM_TEMPLATE = """You are an AI assistant helping a product engineer understand and refine an incident analysis.

You have full context:
- Incident metadata and description
- Raw findings from each analysis agent (logs, code, defects)
- The current synthesized analysis report
- The conversation so far

Answer questions clearly. If your answer suggests a change to the root cause, workaround, or
recommended actions, include a suggested_edit in your response using this exact JSON block:

<suggested_edit>
{{"field": "root_cause|workaround|recommended_actions", "value": "..."}}
</suggested_edit>

Only include a suggested_edit when a specific field change is warranted. Do not suggest edits
for every response."""


def _build_system(incident, sub_reports, current_version) -> str:
    sub_text = "\n\n".join(
        f"[{r.agent}]\n{r.findings}" for r in sub_reports
    ) if sub_reports else "No sub-agent findings available."

    report_text = (
        f"Root cause: {current_version.root_cause}\n"
        f"Workaround: {current_version.workaround}\n"
        f"Actions: {json.dumps([a.model_dump() for a in current_version.recommended_actions], indent=2)}"
    ) if current_version else "No report yet."

    return (
        _SYSTEM_TEMPLATE
        + f"\n\n--- INCIDENT ---\n{incident.title}\n{incident.description}\nMetadata: {incident.metadata}"
        + f"\n\n--- SUB-AGENT FINDINGS ---\n{sub_text}"
        + f"\n\n--- CURRENT REPORT ---\n{report_text}"
    )


def _history_to_messages(history: list[ChatMessage]) -> list:
    msgs = []
    for m in history:
        if m.role == "user":
            msgs.append(HumanMessage(content=m.content))
        else:
            msgs.append(AIMessage(content=m.content))
    return msgs


def _parse_suggested_edit(content: str) -> tuple[str, dict | None]:
    match = re.search(r"<suggested_edit>(.*?)</suggested_edit>", content, re.DOTALL)
    if not match:
        return content, None
    edit_json = match.group(1).strip()
    clean_content = content.replace(match.group(0), "").strip()
    try:
        return clean_content, json.loads(edit_json)
    except json.JSONDecodeError:
        return clean_content, None


async def stream_response(
    message: str,
    incident,
    sub_reports: list,
    current_version,
    history: list[ChatMessage],
) -> AsyncGenerator[str, None]:
    llm = get_llm()

    messages = [
        SystemMessage(content=_build_system(incident, sub_reports, current_version)),
        *_history_to_messages(history),
        HumanMessage(content=message),
    ]

    full_response = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        full_response += token
        yield token

    # After streaming completes, parse and yield the suggested edit marker
    _, suggested_edit = _parse_suggested_edit(full_response)
    if suggested_edit:
        yield f"\n__SUGGESTED_EDIT__{json.dumps(suggested_edit)}"


async def get_full_response(
    message: str,
    incident,
    sub_reports: list,
    current_version,
    history: list[ChatMessage],
) -> tuple[str, dict | None]:
    llm = get_llm()

    messages = [
        SystemMessage(content=_build_system(incident, sub_reports, current_version)),
        *_history_to_messages(history),
        HumanMessage(content=message),
    ]

    response = await llm.ainvoke(messages)
    return _parse_suggested_edit(response.content)
