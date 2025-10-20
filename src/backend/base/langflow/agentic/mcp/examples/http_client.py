"""Example HTTP client for Langflow Agentic MCP Server."""

import requests


class LangflowAgenticHTTPClient:
    """HTTP client for the Langflow Agentic MCP Server."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client.

        Args:
            base_url: Base URL of the server
        """
        self.base_url = base_url.rstrip("/")

    def get_info(self) -> dict:
        """Get server information.

        Returns:
            Server metadata
        """
        response = requests.get(f"{self.base_url}/info", timeout=10)
        response.raise_for_status()
        return response.json()

    def list_tools(self) -> list[dict]:
        """List all available tools.

        Returns:
            List of tool metadata
        """
        response = requests.get(f"{self.base_url}/tools", timeout=10)
        response.raise_for_status()
        return response.json()

    def get_tool(self, tool_name: str) -> dict:
        """Get information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool metadata
        """
        response = requests.get(f"{self.base_url}/tools/{tool_name}", timeout=10)
        response.raise_for_status()
        return response.json()

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool with given arguments.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        payload = {
            "tool_name": tool_name,
            "arguments": arguments,
        }
        response = requests.post(f"{self.base_url}/call", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def stream_tool(self, tool_name: str, arguments: dict):
        """Stream tool execution results using SSE.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Yields:
            Server-sent events
        """
        payload = {
            "tool_name": tool_name,
            "arguments": arguments,
        }
        response = requests.post(
            f"{self.base_url}/stream", json=payload, stream=True, timeout=30
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode("utf-8")
                if decoded_line.startswith("data: "):
                    data = decoded_line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    yield data


def main():
    """Example usage of the HTTP client."""
    client = LangflowAgenticHTTPClient()

    print("=" * 80)
    print("Langflow Agentic MCP - HTTP Client Example")
    print("=" * 80)

    # Get server info
    print("\n1. Getting server info...")
    info = client.get_info()
    print(f"   Server: {info['name']} v{info['version']}")
    print(f"   Tools: {info['tools_count']}")

    # List tools
    print("\n2. Listing tools...")
    tools = client.list_tools()
    print(f"   Found {len(tools)} tools:")
    for tool in tools:
        print(f"   - {tool['name']}")

    # Get specific tool info
    print("\n3. Getting info for 'list_templates'...")
    tool_info = client.get_tool("list_templates")
    print(f"   Description: {tool_info['description'][:60]}...")

    # Call a tool
    print("\n4. Calling 'get_templates_count'...")
    result = client.call_tool("get_templates_count", {})
    print(f"   Success: {result['success']}")
    print(f"   Result: {result['result']} templates")

    # Call tool with parameters
    print("\n5. Calling 'list_templates' with query='agent'...")
    result = client.call_tool(
        "list_templates", {"query": "agent", "fields": ["id", "name"]}
    )
    print(f"   Success: {result['success']}")
    print(f"   Found: {len(result['result'])} templates")
    if result["result"]:
        print(f"   First: {result['result'][0]['name']}")

    # Stream tool execution (example)
    print("\n6. Streaming 'get_all_tags'...")
    print("   Events:")
    for event_data in client.stream_tool("get_all_tags", {}):
        print(f"   - {event_data[:80]}...")

    print("\n" + "=" * 80)
    print("✅ All examples completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
