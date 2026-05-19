"""Tests for flow-run result extraction (the text the agent talks about)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.flow_run import (
    MAX_RESULT_CHARS,
    extract_graph_token_usage,
    extract_run_result_text,
    run_working_flow,
)

MODULE = "langflow.agentic.services.flow_run"


# Lightweight stand-ins mirroring the real shapes:
#   list[RunOutputs] → RunOutputs.outputs: list[ResultData|None]
#   ResultData.messages: list[ChatOutputResponse]; ChatOutputResponse.message: str|list
@dataclass
class _CO:
    message: object


@dataclass
class _Usage:
    input_tokens: object = None
    output_tokens: object = None
    total_tokens: object = None


@dataclass
class _RD:
    messages: list = field(default_factory=list)
    results: object = None
    timedelta: object = None
    token_usage: object = None


@dataclass
class _RO:
    outputs: list = field(default_factory=list)


@dataclass
class _Vertex:
    result: object = None


@dataclass
class _Graph:
    vertices: list = field(default_factory=list)


class TestExtractRunResultText:
    def test_returns_chat_message_text(self):
        run_outputs = [_RO(outputs=[_RD(messages=[_CO(message="woof")])])]
        assert extract_run_result_text(run_outputs) == "woof"

    def test_joins_multiple_messages_in_order(self):
        run_outputs = [
            _RO(outputs=[_RD(messages=[_CO(message="a"), _CO(message="b")])]),
        ]
        assert extract_run_result_text(run_outputs) == "a\nb"

    def test_stringifies_list_message(self):
        run_outputs = [_RO(outputs=[_RD(messages=[_CO(message=["x", "y"])])])]
        out = extract_run_result_text(run_outputs)
        assert "x" in out
        assert "y" in out

    def test_falls_back_to_results_when_no_messages(self):
        run_outputs = [_RO(outputs=[_RD(messages=[], results={"text": "fallback-42"})])]
        assert "fallback-42" in extract_run_result_text(run_outputs)

    def test_returns_sentinel_when_nothing(self):
        assert extract_run_result_text([]) == "(no output)"
        assert extract_run_result_text([_RO(outputs=[])]) == "(no output)"
        assert extract_run_result_text([_RO(outputs=[None])]) == "(no output)"

    def test_caps_result_length(self):
        huge = "z" * (MAX_RESULT_CHARS * 3)
        run_outputs = [_RO(outputs=[_RD(messages=[_CO(message=huge)])])]
        out = extract_run_result_text(run_outputs)
        assert len(out) <= MAX_RESULT_CHARS

    def test_handles_dict_shaped_outputs(self):
        # Real input is pydantic, but be resilient to dict-shaped data too.
        run_outputs = [{"outputs": [{"messages": [{"message": "dict-woof"}]}]}]
        assert extract_run_result_text(run_outputs) == "dict-woof"


class TestExtractGraphTokenUsage:
    """Token usage must be read by walking the graph's vertices.

    It lives on each vertex's ``result.token_usage`` (LLM/Agent vertices),
    NOT on the run_outputs returned by the engine — those only carry the
    *output* vertices, whose token_usage is None by design.
    """

    def test_zeros_when_no_vertices(self):
        assert extract_graph_token_usage(_Graph(vertices=[])) == {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    def test_sums_token_usage_across_vertices(self):
        graph = _Graph(
            vertices=[
                _Vertex(result=_RD(token_usage=_Usage(input_tokens=10, output_tokens=5, total_tokens=15))),
                _Vertex(result=_RD(token_usage=_Usage(input_tokens=2, output_tokens=3, total_tokens=5))),
            ]
        )
        m = extract_graph_token_usage(graph)
        assert m["input_tokens"] == 12
        assert m["output_tokens"] == 8
        assert m["total_tokens"] == 20

    def test_ignores_vertices_without_result_or_usage(self):
        graph = _Graph(
            vertices=[
                _Vertex(result=None),
                _Vertex(result=_RD(token_usage=None)),
                _Vertex(result=_RD(token_usage=_Usage(total_tokens=7))),
            ]
        )
        assert extract_graph_token_usage(graph)["total_tokens"] == 7

    def test_handles_dict_shaped_graph(self):
        graph = {"vertices": [{"result": {"token_usage": {"input_tokens": 4, "total_tokens": 9}}}]}
        m = extract_graph_token_usage(graph)
        assert m["input_tokens"] == 4
        assert m["total_tokens"] == 9

    def test_coerces_non_numeric_safely(self):
        graph = _Graph(vertices=[_Vertex(result=_RD(token_usage=_Usage(total_tokens="nan")))])
        assert extract_graph_token_usage(graph)["total_tokens"] == 0


_FLOW = {"name": "F", "data": {"nodes": [{"id": "ChatInput-1"}], "edges": []}}


class TestRunWorkingFlow:
    @pytest.mark.asyncio
    async def test_success_returns_result_text(self):
        # Token usage comes from the graph's LLM vertex; the ChatOutput the
        # engine returns has token_usage=None by design.
        graph = _Graph(
            vertices=[
                _Vertex(result=_RD(token_usage=_Usage(input_tokens=7, output_tokens=3, total_tokens=10))),
                _Vertex(result=_RD(messages=[_CO(message="woof")], token_usage=None)),
            ]
        )

        async def fake_run(_graph, _flow_id, **_kw):
            await asyncio.sleep(0.02)  # real elapsed time so the timer is exercised
            return ([_RO(outputs=[_RD(messages=[_CO(message="woof")])])], "sess-1")

        with (
            patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock, return_value=graph),
            patch(f"{MODULE}.run_graph_internal", side_effect=fake_run),
        ):
            out = await run_working_flow(flow_data=_FLOW, flow_id="flow-1", user_id="u1")

        assert out["result"] == "woof"
        assert "error" not in out
        m = out["metrics"]
        # Duration is the measured wall time of the run — a real run is never
        # 0.0 (the production "0,0s" bug); it must be a positive number.
        assert isinstance(m["duration_seconds"], float)
        assert m["duration_seconds"] > 0
        assert m["input_tokens"] == 7
        assert m["output_tokens"] == 3
        assert m["total_tokens"] == 10

    @pytest.mark.asyncio
    async def test_run_error_returns_error_envelope_not_exception(self):
        with (
            patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock, return_value=object()),
            patch(f"{MODULE}.run_graph_internal", side_effect=RuntimeError("boom in ChatInput")),
        ):
            out = await run_working_flow(flow_data=_FLOW, flow_id="flow-1", user_id="u1")

        assert "error" in out
        assert "result" not in out

    @pytest.mark.asyncio
    async def test_timeout_returns_error_not_hang(self):
        async def hang(*_a, **_kw):
            await asyncio.sleep(10)

        with (
            patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock, return_value=object()),
            patch(f"{MODULE}.run_graph_internal", side_effect=hang),
            patch(f"{MODULE}.RUN_TIMEOUT_SECONDS", 0.05),
        ):
            out = await run_working_flow(flow_data=_FLOW, flow_id="flow-1", user_id="u1")

        assert "error" in out
        assert "time" in out["error"].lower() or "timed out" in out["error"].lower()

    @pytest.mark.asyncio
    async def test_timeout_still_reports_elapsed_and_partial_token_metrics(self):
        # Bug: a timeout returned only {"error": ...} — no duration, no
        # tokens — so the agent couldn't report the (already billed) cost
        # or how long it ran before timing out.
        graph = _Graph(
            vertices=[
                _Vertex(result=_RD(token_usage=_Usage(input_tokens=5, output_tokens=2, total_tokens=7))),
            ]
        )

        async def hang(*_a, **_kw):
            await asyncio.sleep(10)

        with (
            patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock, return_value=graph),
            patch(f"{MODULE}.run_graph_internal", side_effect=hang),
            patch(f"{MODULE}.RUN_TIMEOUT_SECONDS", 0.05),
        ):
            out = await run_working_flow(flow_data=_FLOW, flow_id="flow-1", user_id="u1")

        assert "error" in out
        m = out["metrics"]
        assert m["duration_seconds"] > 0
        assert m["total_tokens"] == 7
        assert m["input_tokens"] == 5


class TestRunWorkingFlowSecurityGate:
    """Refuse to RUN component code that fails the security scan.

    The generation pipeline scans LLM code, but a flow reaching the run
    engine can carry code that bypassed it (build_flow inline code, an
    overlay .components/*.py, an imported flow). The engine exec's it, so
    run_working_flow must scan first and refuse on any violation —
    deterministic, never reaching build/exec.
    """

    def _flow_with_code(self, code: str) -> dict:
        return {
            "name": "Evil",
            "data": {
                "nodes": [
                    {
                        "id": "Custom-1",
                        "data": {"type": "Custom", "node": {"template": {"code": {"value": code}}}},
                    }
                ],
                "edges": [],
            },
        }

    @pytest.mark.asyncio
    async def test_should_refuse_to_run_when_a_node_has_unsafe_code(self):
        evil = self._flow_with_code('import os\nos.system("rm -rf /")')
        with patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock) as bg:
            out = await run_working_flow(flow_data=evil, flow_id="flow-1", user_id="u1")

        assert "error" in out
        assert "result" not in out
        assert "unsafe" in out["error"].lower()
        bg.assert_not_awaited()  # never reached the graph build / exec

    @pytest.mark.asyncio
    async def test_should_refuse_on_secret_exfiltration_code(self):
        evil = self._flow_with_code('import os\nk = os.environ["OPENAI_API_KEY"]')
        with patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock) as bg:
            out = await run_working_flow(flow_data=evil, flow_id="flow-1", user_id="u1")

        assert "error" in out
        bg.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_should_run_normally_when_code_is_safe(self):
        safe = self._flow_with_code("from math import isqrt\n\nclass C:\n    pass")

        async def fake_run(_g, _f, **_kw):
            return ([], "sess")

        with (
            patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock, return_value=object()) as bg,
            patch(f"{MODULE}.run_graph_internal", side_effect=fake_run),
        ):
            out = await run_working_flow(flow_data=safe, flow_id="flow-1", user_id="u1")

        bg.assert_awaited_once()  # no false positive — safe code still runs
        assert "error" not in out
