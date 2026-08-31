import pytest

from tests.integration.utils import run_single_component


# TODO: Add more tests for MCPToolsComponent
@pytest.mark.asyncio
async def test_mcp_component():
    from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

    # With no tool selected the component reports it, instead of crashing on the
    # `self._tool_cache[None]` lookup its own `if self.tool != ""` guard was written to avoid.
    result = await run_single_component(MCPToolsComponent, inputs={})

    dataframe = next(iter(result.values()))
    assert dataframe.to_dict("records") == [{"error": "You must select a tool"}]
