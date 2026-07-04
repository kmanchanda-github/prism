import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.adapters.data_sources.code_changes import CodeChangesAdapter
from src.agents.confidence import parse_confidence
from src.core.llm import get_llm
from src.models.report import SubReport

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a senior software engineer conducting a code change review for an incident. "
    "You will be given a git diff or code change summary and incident context. "
    "Identify:\n"
    "  1. Which specific code or config changes are most likely to have caused the incident.\n"
    "  2. Any missing safeguards (tests, validation, rollback gates) that would have prevented it.\n"
    "  3. The risk profile of the change (scope, blast radius, reversibility).\n"
    "Be specific — reference file names, line numbers, and config keys from the diff. "
    "Conclude with a confidence score (0.0–1.0) that this change is the root cause. "
    "State it on its own final line in exactly this format: \"Confidence: 0.XX\"."
)


async def run(state) -> dict:
    incident = state.incident
    logger.info("code_analyst: starting for incident=%s", incident.id)

    adapter = CodeChangesAdapter()
    chunks = await adapter.fetch(incident, state.context)

    if not chunks:
        logger.warning("code_analyst: no code change data for incident=%s", incident.id)
        return {"sub_reports": [SubReport(
            agent="code_agent",
            findings="No code change data available for this incident.",
            sources_used=[],
            confidence=0.0,
        )]}

    combined = "\n\n---\n\n".join(
        f"[{c.source}]\n{c.content}" for c in chunks
    )

    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=(
            f"Incident: {incident.title}\n"
            f"Severity: {incident.severity}\n"
            f"Description: {incident.description}\n"
            f"Metadata: {incident.metadata}\n\n"
            f"Code changes:\n{combined}"
        )),
    ])

    if state.token_tracker:
        state.token_tracker.record(
            "code_agent",
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )

    logger.info("code_analyst: completed for incident=%s", incident.id)
    return {"sub_reports": [SubReport(
        agent="code_agent",
        findings=response.content,
        sources_used=[c.source for c in chunks],
        confidence=parse_confidence(response.content),
    )]}
