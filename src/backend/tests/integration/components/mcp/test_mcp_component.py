from tests.integration.utils import run_single_component


async def test_mcp_component():
    from langflow.components.tools.mcp_component import MCPTools

    inputs = {}
    await run_single_component(
        MCPTools,
        inputs=inputs,  # test default inputs
    )
