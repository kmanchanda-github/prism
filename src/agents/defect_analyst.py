import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.adapters.data_sources.defect_db import DefectDbAdapter
from src.core.llm import get_llm
from src.models.report import SubReport

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a defect analyst cross-referencing an incident against a database of known issues. "
    "You will be given known defect records (JSON) and incident context. "
    "Identify:\n"
    "  1. Which known defects match or are related to this incident, and how closely.\n"
    "  2. Whether this incident is a recurrence of a previously seen issue.\n"
    "  3. Whether any open defects (status='open' or 'known') have documented workarounds "
    "     that should have prevented this, and whether they were applied.\n"
    "Reference defect IDs (e.g. DEFECT-1041) explicitly. "
    "Conclude with a confidence score (0.0–1.0) that a known defect is the root cause."
)


async def run(state) -> dict:
    incident = state.incident
    logger.info("defect_analyst: starting for incident=%s", incident.id)

    adapter = DefectDbAdapter()
    chunks = await adapter.fetch(incident, state.context)

    if not chunks:
        logger.warning("defect_analyst: no defect data available for incident=%s", incident.id)
        return {"sub_reports": [SubReport(
            agent="defect_agent",
            findings="No defect database available for this incident.",
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
            f"Known defects:\n{combined}"
        )),
    ])

    if state.token_tracker:
        state.token_tracker.record(
            "defect_agent",
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )

    logger.info("defect_analyst: completed for incident=%s", incident.id)
    return {"sub_reports": [SubReport(
        agent="defect_agent",
        findings=response.content,
        sources_used=[c.source for c in chunks],
        confidence=0.8,
    )]}
