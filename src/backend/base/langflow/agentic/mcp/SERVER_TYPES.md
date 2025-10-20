# Server Types Comparison

The Langflow Agentic MCP system provides **three server types** to accommodate different use cases and integration requirements.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Langflow Agentic MCP                      │
├─────────────────┬──────────────────┬────────────────────────┤
│   MCP Server    │   HTTP/SSE       │   WebSocket           │
│    (stdio)      │    Server        │    Server             │
└─────────────────┴──────────────────┴────────────────────────┘
```

## 1. MCP Server (stdio) - **DEFAULT**

**Communication:** Standard input/output
**Protocol:** MCP (Model Context Protocol)
**Use Case:** Claude Desktop, MCP-compatible clients

### ✅ Pros
- Native MCP protocol compliance
- Works with Claude Desktop out of the box
- Process-based isolation
- No network configuration needed

### ❌ Cons
- Not accessible over network
- Requires process spawning
- Single client per process

### 🚀 Usage

```bash
# Run MCP server (default)
python -m langflow.agentic.mcp.cli

# Or explicitly
python -m langflow.agentic.mcp.server
```

### ⚙️ Configuration (Claude Desktop)

```json
{
  "mcpServers": {
    "langflow-agentic": {
      "command": "python",
      "args": ["-m", "langflow.agentic.mcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/langflow/src/backend/base"
      }
    }
  }
}
```

---

## 2. HTTP/SSE Server - **RECOMMENDED FOR WEB**

**Communication:** HTTP + Server-Sent Events
**Protocol:** REST API + SSE streaming
**Use Case:** Web applications, REST clients, streaming responses

### ✅ Pros
- RESTful API - easy to integrate
- Works with any HTTP client
- Server-Sent Events for streaming
- Multiple concurrent clients
- Network accessible
- Standard web ports

### ❌ Cons
- More complex than stdio
- Requires network configuration
- One-way streaming only

### 🚀 Usage

```bash
# Run HTTP server (port 8000 by default)
python -m langflow.agentic.mcp.cli --http

# Custom host/port
python -m langflow.agentic.mcp.cli --http --host 0.0.0.0 --port 8080

# Development mode with auto-reload
python -m langflow.agentic.mcp.cli --http --reload
```

### 📋 Endpoints

```
GET  /                      - Root information
GET  /info                  - Server information
GET  /tools                 - List all tools
GET  /tools/{tool_name}     - Get specific tool info
POST /call                  - Execute a tool
POST /stream                - Execute with SSE streaming
GET  /health                - Health check
```

### 🔌 Example Client

```python
import requests

# List tools
response = requests.get("http://localhost:8000/tools")
tools = response.json()

# Call a tool
response = requests.post(
    "http://localhost:8000/call",
    json={
        "tool_name": "list_templates",
        "arguments": {"query": "agent"}
    }
)
result = response.json()
```

### 📊 cURL Examples

```bash
# Get server info
curl http://localhost:8000/info

# List all tools
curl http://localhost:8000/tools

# Call a tool
curl -X POST http://localhost:8000/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_templates_count",
    "arguments": {}
  }'

# Stream tool execution
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_all_tags",
    "arguments": {}
  }'
```

---

## 3. WebSocket Server - **RECOMMENDED FOR REAL-TIME**

**Communication:** WebSocket (bidirectional)
**Protocol:** WebSocket with JSON messages
**Use Case:** Real-time applications, bidirectional streaming, dashboards

### ✅ Pros
- Full bidirectional communication
- Real-time updates
- Lower latency than HTTP
- Multiple concurrent clients
- Perfect for dashboards
- Can push updates to clients

### ❌ Cons
- More complex protocol
- Requires WebSocket client
- Connection state management

### 🚀 Usage

```bash
# Run WebSocket server (port 8001 by default)
python -m langflow.agentic.mcp.cli --websocket

# Custom host/port
python -m langflow.agentic.mcp.cli --websocket --host 0.0.0.0 --port 8080

# Development mode with auto-reload
python -m langflow.agentic.mcp.cli --websocket --reload
```

### 📋 Protocol

**Client → Server:**
```json
{
  "action": "list_tools"
}
```

```json
{
  "action": "call_tool",
  "tool_name": "list_templates",
  "arguments": {"query": "agent"}
}
```

**Server → Client:**
```json
{
  "type": "welcome",
  "server": "langflow-agentic",
  "version": "1.0.0"
}
```

```json
{
  "type": "result",
  "tool_name": "list_templates",
  "success": true,
  "result": [...]
}
```

### 🔌 Example Client

```python
import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://localhost:8001/ws") as ws:
        # Receive welcome
        welcome = await ws.recv()
        print(json.loads(welcome))

        # List tools
        await ws.send(json.dumps({"action": "list_tools"}))
        response = await ws.recv()
        print(json.loads(response))

        # Call a tool
        await ws.send(json.dumps({
            "action": "call_tool",
            "tool_name": "get_templates_count",
            "arguments": {}
        }))

        # Receive start event
        start = await ws.recv()

        # Receive result
        result = await ws.recv()
        print(json.loads(result))

asyncio.run(main())
```

---

## Comparison Table

| Feature | MCP (stdio) | HTTP/SSE | WebSocket |
|---------|-------------|----------|-----------|
| **Network Access** | ❌ No | ✅ Yes | ✅ Yes |
| **Multiple Clients** | ❌ No | ✅ Yes | ✅ Yes |
| **Bidirectional** | ✅ Yes | ❌ No* | ✅ Yes |
| **Streaming** | ✅ Yes | ✅ SSE | ✅ Yes |
| **Real-time** | ⚠️ Moderate | ⚠️ Moderate | ✅ Excellent |
| **Complexity** | Low | Low | Moderate |
| **Setup** | Easy | Easy | Moderate |
| **Claude Desktop** | ✅ Native | ❌ No | ❌ No |
| **Web Apps** | ❌ No | ✅ Excellent | ✅ Excellent |
| **Dashboards** | ❌ No | ⚠️ Good | ✅ Excellent |
| **APIs** | ❌ No | ✅ Excellent | ⚠️ Good |
| **Latency** | Low | Moderate | Low |
| **Port Required** | ❌ No | ✅ Yes (8000) | ✅ Yes (8001) |

*SSE is one-way streaming (server → client)

---

## Use Case Recommendations

### 🎯 Choose MCP (stdio) when:
- Integrating with Claude Desktop
- Building MCP-compatible applications
- Don't need network access
- Want simple process-based isolation

### 🌐 Choose HTTP/SSE when:
- Building web applications
- Need RESTful API access
- Have HTTP-only clients
- Want standard web integration
- Need to stream responses

### ⚡ Choose WebSocket when:
- Building real-time dashboards
- Need bidirectional communication
- Want lowest latency
- Building collaborative tools
- Need server-push capability
- Building chat interfaces

---

## Running Multiple Servers

You can run all three servers simultaneously on different ports:

```bash
# Terminal 1: MCP server (stdio)
python -m langflow.agentic.mcp.server

# Terminal 2: HTTP server
python -m langflow.agentic.mcp.cli --http --port 8000

# Terminal 3: WebSocket server
python -m langflow.agentic.mcp.cli --websocket --port 8001
```

---

## Integration Examples

### Example 1: Web Dashboard (HTTP)

```javascript
// Fetch tools
const response = await fetch('http://localhost:8000/tools');
const tools = await response.json();

// Call tool
const result = await fetch('http://localhost:8000/call', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    tool_name: 'list_templates',
    arguments: {query: 'agent'}
  })
});
const data = await result.json();
```

### Example 2: Real-time Dashboard (WebSocket)

```javascript
const ws = new WebSocket('ws://localhost:8001/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'result') {
    updateDashboard(data.result);
  }
};

// Call tool
ws.send(JSON.stringify({
  action: 'call_tool',
  tool_name: 'get_templates_count',
  arguments: {}
}));
```

### Example 3: Claude Desktop (MCP)

See claude_desktop_config.example.json

---

## Performance Characteristics

### MCP (stdio)
- **Throughput:** High (no network overhead)
- **Latency:** Very Low (~1ms)
- **Concurrency:** Single client per process
- **Resource:** Low (one process)

### HTTP/SSE
- **Throughput:** High (async FastAPI)
- **Latency:** Low (~5-50ms)
- **Concurrency:** 1000+ clients
- **Resource:** Moderate (shared process)

### WebSocket
- **Throughput:** Very High (persistent connection)
- **Latency:** Very Low (~2-10ms)
- **Concurrency:** 1000+ clients
- **Resource:** Moderate (connection per client)

---

## Security Considerations

### MCP (stdio)
- ✅ Isolated process
- ✅ No network exposure
- ⚠️ Local system access

### HTTP/SSE
- ⚠️ Network exposed
- ⚠️ Add authentication if needed
- ⚠️ Configure CORS properly
- ✅ Standard security practices

### WebSocket
- ⚠️ Network exposed
- ⚠️ Add authentication if needed
- ⚠️ Validate all messages
- ✅ Persistent connections

---

## Summary

**Quick Decision Matrix:**

- **Claude Desktop Integration?** → Use MCP (stdio)
- **Web API needed?** → Use HTTP
- **Real-time updates?** → Use WebSocket
- **Not sure?** → Start with HTTP (most flexible)

All three servers expose the **same tools** with the **same functionality**, just through different transport layers!
