import pytest

from tests.integration.utils import run_single_component


# TODO: Add more tests for MCPToolsComponent
@pytest.mark.asyncio
async def test_mcp_component():
    from langflow.components.data.mcp_component import MCPToolsComponent

    inputs = {}

    # Expect an error from this call
    with pytest.raises(ValueError, match="None"):
        await run_single_component(
            MCPToolsComponent,
            inputs=inputs,
        )
