from dataclasses import dataclass, field
from typing import Literal

AgentName = Literal[
    "orchestrator", "code_agent", "log_agent", "defect_agent", "synthesizer", "chat"
]

# Approximate cost per million tokens (input/output), by model. These are
# illustrative estimates, not billing-accurate figures — update as provider
# pricing changes. Matched by substring so version suffixes still resolve.
_COST_PER_M_BY_MODEL: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-opus": {"input": 15.00, "output": 75.00},
    "claude-sonnet": {"input": 3.00, "output": 15.00},
    "claude-haiku": {"input": 0.80, "output": 4.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
}
_DEFAULT_COST_PER_M = {"input": 2.50, "output": 10.00}  # fallback for unlisted models


def _cost_per_m(model: str) -> dict[str, float]:
    for key, rates in _COST_PER_M_BY_MODEL.items():
        if key in model:
            return rates
    return _DEFAULT_COST_PER_M


@dataclass
class AgentUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        rates = _cost_per_m(self.model)
        return (
            self.input_tokens * rates["input"]
            + self.output_tokens * rates["output"]
        ) / 1_000_000


@dataclass
class TokenTracker:
    model: str = ""
    usage: dict[AgentName, AgentUsage] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model:
            from src.core.config import get_settings
            self.model = get_settings().llm_model

    def record(self, agent: AgentName, input_tokens: int, output_tokens: int) -> None:
        if agent not in self.usage:
            self.usage[agent] = AgentUsage(model=self.model)
        self.usage[agent].input_tokens += input_tokens
        self.usage[agent].output_tokens += output_tokens

    def totals(self) -> dict:
        total_in = sum(u.input_tokens for u in self.usage.values())
        total_out = sum(u.output_tokens for u in self.usage.values())
        total_cost = sum(u.cost_usd for u in self.usage.values())
        return {
            "per_agent": {k: {"input": v.input_tokens, "output": v.output_tokens, "cost_usd": round(v.cost_usd, 6)} for k, v in self.usage.items()},
            "total_input": total_in,
            "total_output": total_out,
            "total_tokens": total_in + total_out,
            "estimated_cost_usd": round(total_cost, 6),
            "model": self.model,
        }
