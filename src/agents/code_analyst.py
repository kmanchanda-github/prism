from src.models.report import SubReport


async def run(state) -> dict:
    # Phase 2: implement git/repo traversal and code analysis
    return {"sub_reports": [SubReport(
        agent="code_agent",
        findings="Code analysis not yet implemented.",
        sources_used=[],
        confidence=0.0,
    )]}
