"""build_check — Tier-2: construct the graph WITHOUT running it.

`build_graph_from_data` → `Graph.from_payload` instantiates every
component, resolves params and validates wiring/handles at BUILD time;
the LLM only runs later in `vertex.build()`, which we never trigger. So
awaiting the build alone is a deterministic, zero-LLM-token check that
catches "Attribute build_output not found", bad imports, type-mismatched
edges (Edge.__init__ raises) and invalid config.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.flow_graph_build_check import BuildCheckResult, build_check

MODULE = "langflow.agentic.services.flow_graph_build_check"
_FLOW = {"id": "f", "name": "f", "data": {"nodes": [{"id": "A"}], "edges": []}}


class TestBuildCheck:
    @pytest.mark.asyncio
    async def test_should_be_ok_when_the_graph_builds(self):
        with patch(f"{MODULE}.build_graph_from_data", new_callable=AsyncMock, return_value=object()) as bg:
            result = await build_check(flow=_FLOW, flow_id="flow-1", user_id="u1")

        assert isinstance(result, BuildCheckResult)
        assert result.ok is True
        assert result.error is None
        # Delegates the flow's data + ids to the real builder.
        bg.assert_awaited_once()
        assert bg.await_args.args[0] == "flow-1"
        assert bg.await_args.args[1] == _FLOW["data"]

    @pytest.mark.asyncio
    async def test_should_report_the_deterministic_build_error_when_construction_raises(self):
        with patch(
            f"{MODULE}.build_graph_from_data",
            new_callable=AsyncMock,
            side_effect=ValueError("Attribute build_output not found in PrimeChecker"),
        ):
            result = await build_check(flow=_FLOW, flow_id="flow-1", user_id="u1")

        assert result.ok is False
        assert result.error is not None
        assert "build_output not found" in result.error

    @pytest.mark.asyncio
    async def test_should_not_crash_on_an_unexpected_error(self):
        with patch(
            f"{MODULE}.build_graph_from_data",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom deep in graph"),
        ):
            result = await build_check(flow=_FLOW, flow_id="flow-1", user_id="u1")

        assert result.ok is False
        assert "boom deep in graph" in (result.error or "")
