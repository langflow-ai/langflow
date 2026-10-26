import pytest
from langflow.services.evaluations.estimate_model import (
    DEFAULT_ANSWER_TOKENS,
    DatasetStats,
    estimate_flow,
    estimate_judges,
    flow_llm_nodes,
)

PRICED = {"name": "cheap", "provider": "OpenAI", "metadata": {"cost_per_million_in": 1.0, "cost_per_million_out": 2.0}}
UNPRICED = {"name": "mystery", "provider": "Nowhere", "metadata": {}}
STATS = DatasetStats(items=10, input_chars=400, expected_chars=200, with_expected=10)


def _node(node_type: str, template: dict) -> dict:
    return {"data": {"type": node_type, "node": {"template": template}}}


def _flow(*nodes: dict) -> dict:
    return {"nodes": list(nodes)}


class TestFlowNodes:
    def test_should_find_llm_components_and_their_prompt_text(self):
        flow = _flow(
            _node("ChatInput", {}),
            _node("Prompt", {"template": {"value": "x" * 80}}),
            _node("LanguageModelComponent", {"model": {"value": [PRICED]}}),
            _node("Agent", {"model": {"value": [PRICED]}, "system_prompt": {"value": "y" * 40}}),
        )
        nodes = flow_llm_nodes(flow)
        assert [node.agent for node in nodes] == [False, True]
        assert all(node.prompt_chars == 120 for node in nodes)

    def test_should_ignore_a_model_field_without_selection(self):
        assert flow_llm_nodes(_flow(_node("LanguageModelComponent", {"model": {"value": None}}))) == []


class TestFlowEstimate:
    def test_should_return_zero_for_a_flow_without_llm(self):
        result = estimate_flow([], STATS)
        assert (result.tokens_low, result.tokens_high, result.cost_low) == (0, 0, 0.0)

    def test_should_price_a_single_llm_range(self):
        result = estimate_flow(flow_llm_nodes(_flow(_node("LLM", {"model": {"value": [PRICED]}}))), STATS)
        # input 400 chars -> 100 tokens; answers 20 chars -> 5 tokens each, 50 total at the low end.
        assert result.tokens_low == 150
        assert result.tokens_high == 100 + DEFAULT_ANSWER_TOKENS * 10
        assert result.cost_low == pytest.approx((100 * 1 + 50 * 2) / 1_000_000)
        assert result.cost_high > result.cost_low

    def test_should_assume_several_calls_for_an_agent(self):
        plain = estimate_flow(flow_llm_nodes(_flow(_node("LLM", {"model": {"value": [PRICED]}}))), STATS)
        agent = estimate_flow(flow_llm_nodes(_flow(_node("Agent", {"model": {"value": [PRICED]}}))), STATS)
        assert agent.tokens_low == plain.tokens_low
        assert agent.tokens_high == 3 * plain.tokens_high

    def test_should_report_unknown_cost_instead_of_guessing(self):
        result = estimate_flow(flow_llm_nodes(_flow(_node("LLM", {"model": {"value": [UNPRICED]}}))), STATS)
        assert result.cost_low is None
        assert result.unpriced == ["mystery"]
        assert result.tokens_low > 0


class TestJudgeEstimate:
    def test_should_bound_the_judge_output_by_its_token_cap(self):
        scorers = [{"type": "llm_judge", "name": "j", "config": {"model": [PRICED]}}]
        result = estimate_judges(scorers, STATS, max_output_tokens=300)
        assert result.tokens_high > result.tokens_low > 0
        assert result.tokens_high >= 300 * STATS.items

    def test_should_skip_text_scorers(self):
        assert estimate_judges([{"type": "exact_match", "name": "e"}], STATS, 300).tokens_high == 0
