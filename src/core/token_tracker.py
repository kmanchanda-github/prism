from dataclasses import dataclass, field
from typing import Literal

AgentName = Literal[
    "orchestrator", "code_agent", "log_agent", "defect_agent", "synthesizer", "chat"
]

# Cost per million tokens (input/output) for claude-sonnet-4-6
_COST_PER_M = {"input": 3.0, "output": 15.0}


@dataclass
class AgentUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * _COST_PER_M["input"]
            + self.output_tokens * _COST_PER_M["output"]
        ) / 1_000_000


@dataclass
class TokenTracker:
    usage: dict[AgentName, AgentUsage] = field(default_factory=dict)

    def record(self, agent: AgentName, input_tokens: int, output_tokens: int) -> None:
        if agent not in self.usage:
            self.usage[agent] = AgentUsage()
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
        }
