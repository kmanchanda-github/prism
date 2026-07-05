"""
Main LangGraph orchestrator.

Flow:
  parse_incident → route_decision → [parallel] log_agent / code_agent / defect_agent
    → synthesizer → quality_check → notify → END
"""
from typing import Annotated, Any
import operator

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Send
from pydantic import BaseModel

from src.core.config import get_yaml_config
from src.core.llm import get_llm
from src.core.token_tracker import TokenTracker
from src.models.incident import Incident
from src.models.report import SubReport


class AnalysisState(BaseModel):
    incident: Incident
    active_agents: list[str] = []
    sub_reports: Annotated[list[SubReport], operator.add] = []
    root_cause: str = ""
    workaround: str = ""
    recommended_actions: list[dict] = []
    confidence_score: float = 0.0
    retry_count: int = 0
    token_tracker: Any = None  # TokenTracker (not serialisable as Pydantic)
    context: dict = {}         # runtime context: log_bundle_path, etc.
    notify_channels: list[str] = []
    error: str | None = None
    langsmith_run_id: str | None = None  # synthesizer's LLM call trace ID, for later feedback attachment


def _llm():
    return get_llm()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def parse_incident(state: AnalysisState) -> dict:
    state.token_tracker = TokenTracker()
    return {"token_tracker": state.token_tracker}


async def route_decision(state: AnalysisState) -> dict:
    llm = _llm()
    system = SystemMessage(content=(
        "You are an incident triage router. Given incident metadata and description, "
        "decide which analysis agents to activate. "
        "Reply with a JSON list from: [\"log_agent\", \"code_agent\", \"defect_agent\"]. "
        "Always include log_agent if log data may be relevant. "
        "Example: [\"log_agent\", \"defect_agent\"]"
    ))
    human = HumanMessage(content=(
        f"Incident: {state.incident.title}\n"
        f"Severity: {state.incident.severity}\n"
        f"Description: {state.incident.description}\n"
        f"Metadata: {state.incident.metadata}"
    ))
    response = await llm.ainvoke([system, human])
    state.token_tracker.record(
        "orchestrator",
        response.usage_metadata.get("input_tokens", 0),
        response.usage_metadata.get("output_tokens", 0),
    )

    import json, re
    match = re.search(r"\[.*?\]", response.content, re.DOTALL)
    agents = json.loads(match.group()) if match else ["log_agent"]
    return {"active_agents": agents}


def fan_out(state: AnalysisState) -> list[Send]:
    """Dispatch each active agent as a parallel LangGraph Send."""
    return [Send(agent, state) for agent in state.active_agents]


async def synthesizer(state: AnalysisState) -> dict:
    from src.agents.synthesizer import run_synthesis
    return await run_synthesis(state)


async def quality_check(state: AnalysisState) -> dict:
    cfg = get_yaml_config().get("analysis", {})
    threshold = cfg.get("confidence_threshold", 0.7)
    max_retries = cfg.get("max_retries", 2)

    if state.confidence_score >= threshold or state.retry_count >= max_retries:
        return {}
    return {"retry_count": state.retry_count + 1, "sub_reports": []}


def should_retry(state: AnalysisState) -> str:
    cfg = get_yaml_config().get("analysis", {})
    threshold = cfg.get("confidence_threshold", 0.7)
    max_retries = cfg.get("max_retries", 2)
    if state.confidence_score < threshold and state.retry_count < max_retries:
        return "route_decision"
    return "notify"


async def notify(state: AnalysisState) -> dict:
    # Notification is handled by the Celery task after the graph completes
    # so this node is a no-op placeholder for future direct-graph triggers.
    return {}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(AnalysisState)

    g.add_node("parse_incident", parse_incident)
    g.add_node("route_decision", route_decision)
    g.add_node("log_agent", _import_agent("log_analyst"))
    g.add_node("code_agent", _import_agent("code_analyst"))
    g.add_node("defect_agent", _import_agent("defect_analyst"))
    g.add_node("synthesizer", synthesizer)
    g.add_node("quality_check", quality_check)
    g.add_node("notify", notify)

    g.set_entry_point("parse_incident")
    g.add_edge("parse_incident", "route_decision")
    g.add_conditional_edges("route_decision", fan_out, ["log_agent", "code_agent", "defect_agent"])
    g.add_edge("log_agent", "synthesizer")
    g.add_edge("code_agent", "synthesizer")
    g.add_edge("defect_agent", "synthesizer")
    g.add_edge("synthesizer", "quality_check")
    g.add_conditional_edges("quality_check", should_retry, {"route_decision": "route_decision", "notify": "notify"})
    g.add_edge("notify", END)

    return g.compile()


def _import_agent(module_name: str):
    """Lazily import agent node functions to avoid circular imports."""
    import importlib
    mod = importlib.import_module(f"src.agents.{module_name}")
    return mod.run
