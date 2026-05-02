from langchain_core.messages import HumanMessage, SystemMessage

from src.adapters.data_sources.log_bundle import LogBundleAdapter
from src.core.llm import get_llm
from src.models.report import SubReport


async def run(state) -> dict:
    incident = state.incident
    llm = get_llm()

    adapter = LogBundleAdapter()
    chunks = await adapter.fetch(incident, state.context)

    if not chunks:
        return {"sub_reports": [SubReport(
            agent="log_agent",
            findings="No log data available.",
            sources_used=[],
            confidence=0.0,
        )]}

    combined = "\n\n---\n\n".join(
        f"[{c.source}]\n{c.content}" for c in chunks[:10]  # cap at 10 chunks
    )

    system = SystemMessage(content=(
        "You are a log analysis expert. Analyze the provided logs for the given incident. "
        "Identify error patterns, anomalies, timing issues, and root cause indicators. "
        "Be specific about line references. Conclude with a confidence score (0.0-1.0) "
        "that these logs contain enough signal for root cause determination."
    ))
    human = HumanMessage(content=(
        f"Incident: {incident.title}\nDescription: {incident.description}\n\n"
        f"Logs:\n{combined}"
    ))

    response = await llm.ainvoke([system, human])
    state.token_tracker.record(
        "log_agent",
        response.usage_metadata.get("input_tokens", 0),
        response.usage_metadata.get("output_tokens", 0),
    )

    return {"sub_reports": [SubReport(
        agent="log_agent",
        findings=response.content,
        sources_used=[c.source for c in chunks],
        confidence=0.7,  # TODO: parse from structured response
    )]}
