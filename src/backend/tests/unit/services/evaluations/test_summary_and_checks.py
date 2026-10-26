import json
from pathlib import Path
from uuid import uuid4

import pytest
from langflow.services.database.models.evaluation import EvaluationResult
from langflow.services.evaluations.flow_checks import check_flow, resolve_output_vertex
from langflow.services.evaluations.summary import build_summary, percentile

ECHO_FLOW = Path(__file__).resolve().parents[3] / "data" / "chat_echo_no_llm.json"


def _result(position, *, value=None, passed=None, error=None, tokens=None, cost=None, duration=100):
    scores = {} if value is None else {"exact": {"value": value}}
    return EvaluationResult(
        run_id=uuid4(),
        position=position,
        input={"text": "q"},
        scores=scores,
        passed=passed,
        error=error,
        tokens_flow=tokens,
        cost_flow=cost,
        duration_ms=duration,
    )


class TestSummary:
    def test_should_use_nearest_rank_percentiles(self):
        assert percentile([], 0.5) is None
        assert percentile([5.0], 0.9) == 5.0
        assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9

    def test_should_aggregate_scores_pass_rate_and_tokens(self):
        results = [
            _result(0, value=1.0, passed=True, tokens=10, cost=0.01),
            _result(1, value=0.0, passed=False, tokens=20, cost=0.02),
            _result(2, error="boom", passed=False),
        ]
        summary = build_summary(results, ["exact"])
        assert summary["scores"]["exact"]["mean"] == 0.5
        assert summary["pass_rate"] == pytest.approx(1 / 3, abs=1e-4)
        assert summary["tokens"] == {"flow": 30, "judge": 0, "total": 30}
        assert summary["cost_usd"]["flow"] == pytest.approx(0.03)
        assert summary["rows"] == {"total": 3, "errored": 1, "decided": 3}

    def test_should_not_report_a_partial_cost_as_total(self):
        results = [_result(0, tokens=10, cost=0.01), _result(1, tokens=10, cost=None)]
        summary = build_summary(results, ["exact"])
        assert summary["cost_usd"]["flow"] is None
        assert summary["cost_usd"]["complete"] is False

    def test_should_handle_a_run_with_no_results(self):
        summary = build_summary([], ["exact"])
        assert summary["pass_rate"] is None
        assert summary["scores"]["exact"]["mean"] is None


def _node(node_id, node_type, **extra):
    inner = {"display_name": node_type, "template": {}, "outputs": extra.pop("outputs", [])}
    inner.update(extra)
    return {"id": node_id, "type": "genericNode", "data": {"id": node_id, "type": node_type, "node": inner}}


class TestFlowChecks:
    def test_should_accept_a_chat_flow(self):
        flow = {"nodes": [_node("ChatInput-a", "ChatInput"), _node("ChatOutput-b", "ChatOutput")], "edges": []}
        report = check_flow(flow)
        assert report.blocking == []
        assert resolve_output_vertex(flow, None) == "ChatOutput-b"

    @pytest.mark.parametrize(
        ("nodes", "code"),
        [
            ([], "empty_flow"),
            ([_node("ChatOutput-b", "ChatOutput")], "no_input"),
            ([_node("ChatInput-a", "ChatInput")], "no_output"),
            (
                [
                    _node("ChatInput-a", "ChatInput"),
                    _node("ChatOutput-b", "ChatOutput"),
                    _node("TextOutput-c", "TextOutput"),
                ],
                "multiple_outputs",
            ),
        ],
    )
    def test_should_block_unsupported_shapes(self, nodes, code):
        report = check_flow({"nodes": nodes, "edges": []})
        assert code in {issue.code for issue in report.blocking}

    def test_should_accept_multiple_outputs_once_one_is_chosen(self):
        nodes = [
            _node("ChatInput-a", "ChatInput"),
            _node("ChatOutput-b", "ChatOutput"),
            _node("TextOutput-c", "TextOutput"),
        ]
        report = check_flow({"nodes": nodes, "edges": []}, "TextOutput-c")
        assert report.blocking == []
        stale = check_flow({"nodes": nodes, "edges": []}, "Gone-1")
        assert [issue.code for issue in stale.blocking] == ["output_not_found"]

    def test_should_block_human_in_the_loop(self):
        nodes = [_node("ChatInput-a", "ChatInput"), _node("human", "HumanInput"), _node("ChatOutput-b", "ChatOutput")]
        report = check_flow({"nodes": nodes, "edges": [{"source": "human", "target": "ChatOutput-b"}]})
        assert "human_in_the_loop" in {issue.code for issue in report.blocking}

    def test_should_warn_about_external_actions_memory_and_frozen(self):
        nodes = [
            _node("ChatInput-a", "ChatInput"),
            _node("ChatOutput-b", "ChatOutput"),
            _node("Gmail-c", "GmailSendEmail"),
            _node("Redis-d", "RedisChatMemory", outputs=[{"name": "memory", "types": ["Memory"]}]),
            _node("Prompt-e", "Prompt", frozen=True),
        ]
        warnings = {issue.code: issue.components for issue in check_flow({"nodes": nodes, "edges": []}).warnings}
        assert warnings["external_actions"] == ["GmailSendEmail"]
        assert warnings["external_memory"] == ["RedisChatMemory"]
        assert warnings["frozen_components"] == ["Prompt"]

    def test_should_ignore_sticky_notes(self):
        note = {"id": "note-1", "type": "noteNode", "data": {"id": "note-1", "type": "note", "node": {}}}
        flow = {"nodes": [note, _node("ChatInput-a", "ChatInput"), _node("ChatOutput-b", "ChatOutput")], "edges": []}
        assert check_flow(flow).blocking == []

    def test_should_accept_the_bundled_echo_flow(self):
        flow = json.loads(ECHO_FLOW.read_text(encoding="utf-8"))
        assert check_flow(flow["data"]).blocking == []
