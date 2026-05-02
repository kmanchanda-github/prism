from src.models.report import SubReport


async def run(state) -> dict:
    # Phase 2: implement Jira/Salesforce defect querying
    return {"sub_reports": [SubReport(
        agent="defect_agent",
        findings="Defect analysis not yet implemented.",
        sources_used=[],
        confidence=0.0,
    )]}
