#!/usr/bin/env python3
"""
Example script demonstrating how to create and serve a Langflow graph via MCP.

This script creates a simple echo flow that can be served using the MCP protocol.

Usage:
    # Serve via MCP with stdio transport (for local tools)
    langflow serve examples/mcp_serve_example.py --mcp --mcp-transport stdio

    # Serve via MCP with SSE transport (for web-based clients)  
    langflow serve examples/mcp_serve_example.py --mcp --mcp-transport sse --port 8000

    # Serve via MCP with custom server name
    langflow serve examples/mcp_serve_example.py --mcp --mcp-name "Echo Bot MCP Server"
"""

from langflow.components.input_output.chat import ChatInput
from langflow.components.input_output.chat_output import ChatOutput
from langflow.graph.graph.base import Graph


def create_echo_flow():
    """Create a simple echo flow that returns the input as output."""
    # Create input component
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(
        input_value="Hello, this is an echo bot! Say something to me.",
        sender="User",
        session_id="echo_session"
    )
    
    # Create output component 
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(
        input_value=chat_input.message_response,
        sender="Echo Bot"
    )
    
    # Create and return the graph
    return Graph(chat_input, chat_output)


def create_processing_flow():
    """Create a flow that processes text by adding a prefix."""
    from langflow.components.processing.text import TextProcessor
    
    # Create input component
    text_input = ChatInput(_id="text_input")
    text_input.set(
        input_value="Enter text to process",
        sender="User",
        session_id="processing_session"
    )
    
    # Create text processor (if available)
    # This is a simplified example - in real use you'd use actual Langflow components
    processed_text = f"PROCESSED: {text_input.message_response}"
    
    # Create output component
    text_output = ChatOutput(_id="text_output") 
    text_output.set(
        input_value=processed_text,
        sender="Processor Bot"
    )
    
    return Graph(text_input, text_output)


# The main graph that will be served
# Langflow CLI looks for a variable named 'graph'
graph = create_echo_flow()


if __name__ == "__main__":
    print("Echo Flow MCP Example")
    print("=" * 40)
    print("This script creates a simple echo flow that can be served via MCP.")
    print()
    print("To serve this flow via MCP, use:")
    print("  langflow serve examples/mcp_serve_example.py --mcp")
    print()
    print("Available MCP transports:")
    print("  --mcp-transport stdio     # For local tool integration")
    print("  --mcp-transport sse       # For web-based clients")
    print("  --mcp-transport websocket # For real-time applications")
    print()
    print("Example commands:")
    print("  langflow serve examples/mcp_serve_example.py --mcp --mcp-transport stdio")
    print("  langflow serve examples/mcp_serve_example.py --mcp --mcp-transport sse --port 8000")
    print()
    
    # Test the flow locally
    try:
        print("Testing the flow locally...")
        result = graph.run(inputs={"input_value": "Hello from local test!"})
        print(f"Result: {result}")
        print("✓ Flow test successful!")
    except Exception as e:
        print(f"✗ Flow test failed: {e}")
        print("This might be due to missing dependencies or component issues.")