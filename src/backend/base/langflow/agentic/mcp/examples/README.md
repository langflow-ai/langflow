# Client Examples

Example clients demonstrating how to connect to the Langflow Agentic MCP Server.

## HTTP Client

Connects to the HTTP/SSE server.

**Run the server:**
```bash
python -m langflow.agentic.mcp.cli --http
```

**Run the example:**
```bash
python -m langflow.agentic.mcp.examples.http_client
```

## WebSocket Client

Connects to the WebSocket server for bidirectional communication.

**Run the server:**
```bash
python -m langflow.agentic.mcp.cli --websocket
```

**Run the example:**
```bash
python -m langflow.agentic.mcp.examples.websocket_client
```

## Features Demonstrated

- Server info retrieval
- Listing available tools
- Getting tool details
- Calling tools with arguments
- Streaming responses (HTTP)
- Bidirectional communication (WebSocket)
