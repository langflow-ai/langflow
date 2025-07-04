#!/usr/bin/env python3
"""Example script demonstrating how to create and serve a Langflow graph via MCP.

This script creates a simple echo flow that can be served using the MCP protocol.

Usage examples:
# Serve via MCP with SSE transport (for LLM clients) 
langflow serve examples/mcp_serve_example.py --mcp --mcp-transport sse

# Serve via MCP with custom port
langflow serve examples/mcp_serve_example.py --mcp --port 8000

# Serve via MCP with custom server name
langflow serve examples/mcp_serve_example.py --mcp --mcp-name "Echo Bot MCP Server"
"""

from langflow.custom import Component
from langflow.inputs import StrInput
from langflow.outputs import StrOutput
from langflow.schema import Data


class EchoComponent(Component):
    """A simple component that echoes back the input message."""

    display_name = "Echo"
    description = "Echoes back the input message with a greeting"
    icon = "📢"

    inputs = [
        StrInput(
            name="message",
            display_name="Message",
            info="The message to echo back",
            value="Hello, World!"
        ),
    ]

    outputs = [
        StrOutput(
            name="echoed_message",
            display_name="Echoed Message"
        ),
    ]

    def build(self, message: str) -> Data:
        """Echo the input message with a greeting."""
        echoed = f"Echo: {message}"

        self.status = echoed
        return Data(value=echoed)


# Create the flow
def create_echo_flow():
    """Create a simple echo flow for MCP serving."""
    from langflow.graph import Graph

    # Create a new graph
    graph = Graph()

    # Add the echo component
    echo_node = graph.add_node(EchoComponent())

    # Set the echo component as both input and output
    graph.set_input_node(echo_node)
    graph.set_output_node(echo_node)

    return graph


# Main entry point
if __name__ == "__main__":
    # Create and display information about the flow
    flow = create_echo_flow()

    print("Echo Flow MCP Example")
    print("=" * 50)
    print("This script creates a simple echo flow that can be served via MCP.")
    print()
    print("To serve this flow via MCP, use:")
    print("  langflow serve examples/mcp_serve_example.py --mcp")
    print()
    print("Available MCP transport:")
    print("  --mcp-transport sse       # For LLM clients (default)")
    print()
    print("Example commands:")
    print("  langflow serve examples/mcp_serve_example.py --mcp --mcp-transport sse")
    print("  langflow serve examples/mcp_serve_example.py --mcp --port 8000")
    print()
    print("Once running, the MCP server will expose this echo flow as a tool")
    print("that LLM clients can discover and execute.")
