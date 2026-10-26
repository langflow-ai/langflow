"""Rough per-row token and cost model, from the flow's LLM components, the judge and the dataset size.

The numbers are a range, not a promise: characters are converted at ~4 per token and the
answer length is guessed from the expected outputs. Prices come from the model catalog only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langflow.services.evaluations.pricing import model_identity, prices_per_million
from langflow.services.evaluations.scorers.llm_judge import DEFAULT_RUBRIC, SYSTEM_PROMPT

CHARS_PER_TOKEN = 4
DEFAULT_ANSWER_TOKENS = 256
JUDGE_REASON_TOKENS = 60
# Agents call the model several times per question (tool calls, retries); the high end assumes three.
AGENT_CALLS_HIGH = 3
AGENT_TYPES = frozenset({"Agent"})
PROMPT_FIELDS = ("system_prompt", "system_message", "template", "instructions")


@dataclass(frozen=True)
class DatasetStats:
    items: int
    input_chars: int
    expected_chars: int
    with_expected: int


@dataclass(frozen=True)
class LlmNode:
    model: dict[str, Any]
    prompt_chars: int
    agent: bool


@dataclass
class TokenRange:
    tokens_low: int = 0
    tokens_high: int = 0
    cost_low: float | None = 0.0
    cost_high: float | None = 0.0
    unpriced: list[str] = field(default_factory=list)

    def add(self, model: dict[str, Any], low: tuple[float, float], high: tuple[float, float]) -> None:
        """Add (input, output) token counts for one model at the low and high end."""
        self.tokens_low += int(low[0] + low[1])
        self.tokens_high += int(high[0] + high[1])
        prices = prices_per_million(model)
        if prices is None:
            self.cost_low = self.cost_high = None
            name = str(model.get("name") or "unknown")
            if name not in self.unpriced:
                self.unpriced.append(name)
            return
        price_in, price_out = prices
        if self.cost_low is not None and self.cost_high is not None:
            self.cost_low += (low[0] * price_in + low[1] * price_out) / 1_000_000
            self.cost_high += (high[0] * price_in + high[1] * price_out) / 1_000_000


def _tokens(chars: float) -> float:
    return chars / CHARS_PER_TOKEN


def _prompt_chars(template: dict[str, Any]) -> int:
    total = 0
    for name in PROMPT_FIELDS:
        value = (template.get(name) or {}).get("value") if isinstance(template.get(name), dict) else None
        if isinstance(value, str):
            total += len(value)
    return total


def flow_llm_nodes(flow_data: dict[str, Any]) -> list[LlmNode]:
    nodes = flow_data.get("nodes") or []
    shared_prompt = sum(
        _prompt_chars(((node.get("data") or {}).get("node") or {}).get("template") or {})
        for node in nodes
        if isinstance(node, dict)
    )
    found: list[LlmNode] = []
    for node in nodes:
        data = (node.get("data") or {}) if isinstance(node, dict) else {}
        template = (data.get("node") or {}).get("template") or {}
        model_field = template.get("model")
        model = model_identity(model_field.get("value")) if isinstance(model_field, dict) else None
        if model is None:
            continue
        found.append(LlmNode(model=model, prompt_chars=shared_prompt, agent=data.get("type") in AGENT_TYPES))
    return found


def estimate_flow(nodes: list[LlmNode], stats: DatasetStats) -> TokenRange:
    total = TokenRange()
    avg_answer_chars = stats.expected_chars / stats.with_expected if stats.with_expected else 0
    answer_low = _tokens(avg_answer_chars) if avg_answer_chars else DEFAULT_ANSWER_TOKENS / 4
    answer_high = max(DEFAULT_ANSWER_TOKENS, answer_low * 2)
    for node in nodes:
        input_tokens = _tokens(node.prompt_chars * stats.items + stats.input_chars)
        calls_high = AGENT_CALLS_HIGH if node.agent else 1
        total.add(
            node.model,
            (input_tokens, answer_low * stats.items),
            (input_tokens * calls_high, answer_high * stats.items * calls_high),
        )
    return total


def estimate_judges(scorers: list[dict[str, Any]], stats: DatasetStats, max_output_tokens: int) -> TokenRange:
    total = TokenRange()
    fixed_chars = len(SYSTEM_PROMPT) + 120
    for spec in scorers:
        if spec.get("type") != "llm_judge":
            continue
        model = model_identity((spec.get("config") or {}).get("model"))
        if model is None:
            continue
        rubric = (spec.get("config") or {}).get("rubric") or DEFAULT_RUBRIC
        # The judged answer is assumed about as long as the expected one.
        row_chars = stats.items * (fixed_chars + len(rubric)) + stats.input_chars + 2 * stats.expected_chars
        input_tokens = _tokens(row_chars)
        total.add(
            model,
            (input_tokens, JUDGE_REASON_TOKENS * stats.items),
            (input_tokens * 1.5, max_output_tokens * stats.items),
        )
    return total
