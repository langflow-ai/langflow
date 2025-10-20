"""Example WebSocket client for Langflow Agentic MCP Server."""

import asyncio
import json

import websockets


class LangflowAgenticWebSocketClient:
    """WebSocket client for the Langflow Agentic MCP Server."""

    def __init__(self, url: str = "ws://localhost:8001/ws"):
        """Initialize the client.

        Args:
            url: WebSocket URL
        """
        self.url = url
        self.websocket = None

    async def connect(self):
        """Connect to the WebSocket server."""
        self.websocket = await websockets.connect(self.url)
        # Receive welcome message
        welcome = await self.websocket.recv()
        return json.loads(welcome)

    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        if self.websocket:
            await self.websocket.close()

    async def send_action(self, action: str, **kwargs):
        """Send an action to the server.

        Args:
            action: Action name
            **kwargs: Additional parameters
        """
        payload = {"action": action, **kwargs}
        await self.websocket.send(json.dumps(payload))

    async def receive_response(self):
        """Receive a response from the server.

        Returns:
            Response data
        """
        message = await self.websocket.recv()
        return json.loads(message)

    async def get_info(self) -> dict:
        """Get server information.

        Returns:
            Server metadata
        """
        await self.send_action("get_info")
        response = await self.receive_response()
        return response["data"]

    async def list_tools(self) -> list[dict]:
        """List all available tools.

        Returns:
            List of tool metadata
        """
        await self.send_action("list_tools")
        response = await self.receive_response()
        return response["data"]

    async def get_tool(self, tool_name: str) -> dict:
        """Get information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool metadata
        """
        await self.send_action("get_tool", tool_name=tool_name)
        response = await self.receive_response()
        return response["data"]

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool with given arguments.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        await self.send_action("call_tool", tool_name=tool_name, arguments=arguments)

        # Receive start event
        start_event = await self.receive_response()
        assert start_event["type"] == "start"

        # Receive result
        result_event = await self.receive_response()
        return result_event

    async def ping(self) -> bool:
        """Send a ping to check connection.

        Returns:
            True if pong received
        """
        await self.send_action("ping")
        response = await self.receive_response()
        return response["type"] == "pong"


async def main():
    """Example usage of the WebSocket client."""
    client = LangflowAgenticWebSocketClient()

    print("=" * 80)
    print("Langflow Agentic MCP - WebSocket Client Example")
    print("=" * 80)

    try:
        # Connect
        print("\n1. Connecting to server...")
        welcome = await client.connect()
        print(f"   Connected to: {welcome['server']} v{welcome['version']}")
        print(f"   Available tools: {welcome['tools_count']}")

        # Get server info
        print("\n2. Getting server info...")
        info = await client.get_info()
        print(f"   Name: {info['name']}")
        print(f"   Description: {info['description'][:60]}...")

        # List tools
        print("\n3. Listing tools...")
        tools = await client.list_tools()
        print(f"   Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}")

        # Get specific tool
        print("\n4. Getting info for 'list_templates'...")
        tool_info = await client.get_tool("list_templates")
        print(f"   Description: {tool_info['description'][:60]}...")
        print(f"   Module: {tool_info['module_path']}")

        # Call a tool
        print("\n5. Calling 'get_templates_count'...")
        result = await client.call_tool("get_templates_count", {})
        print(f"   Success: {result['success']}")
        print(f"   Result: {result['result']} templates")

        # Call tool with parameters
        print("\n6. Calling 'list_templates' with query='agent'...")
        result = await client.call_tool(
            "list_templates", {"query": "agent", "fields": ["id", "name"]}
        )
        print(f"   Success: {result['success']}")
        print(f"   Found: {len(result['result'])} templates")
        if result["result"]:
            print(f"   First: {result['result'][0]['name']}")

        # Ping test
        print("\n7. Testing connection with ping...")
        pong = await client.ping()
        print(f"   Pong received: {pong}")

        print("\n" + "=" * 80)
        print("✅ All examples completed!")
        print("=" * 80 + "\n")

    finally:
        # Disconnect
        await client.disconnect()
        print("Disconnected from server.")


if __name__ == "__main__":
    asyncio.run(main())
