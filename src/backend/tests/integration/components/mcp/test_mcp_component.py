from tests.integration.utils import run_single_component


async def test_mcp_component():
    from langflow.components.data.mcp_component import MCPToolsComponent

    inputs = {}
    await run_single_component(
        MCPToolsComponent,
        inputs=inputs,  # test default inputs
    )
