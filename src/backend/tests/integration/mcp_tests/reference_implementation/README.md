# Langflow MCP Reference Implementation

This directory contains a **self-contained playground** for testing the Model Context Protocol (MCP) end-to-end in three distinct transports:

* **Streamable-HTTP** (2025-03-26 spec)  → `/mcp`
* **HTTP + SSE** (2024-11-05 spec)       → `/sse`
* **STDIO** (2025-03-26 spec)            → child-process pipes

## Contents

| File | Description |
|------|-------------|
| `mcp_sse_reference.js`   | Node server exposing both Streamable-HTTP and HTTP + SSE endpoints on the same port. |
| `mcp_stdio_reference.js` | Node server that speaks the MCP **stdio** transport. Useful when a host needs to spawn tools as subprocesses. |
| `demo_mcp_client.py`  | Minimal Python client that can talk to any of the three transports; runs the full lifecycle (initialize → list tools → optional `echo` call → shutdown). |

All three servers expose identical **tools**, **resources** and **prompts** so you can exercise identical behaviour across transports.

## Prerequisites

* **Node ≥ 18** with ESM enabled
* **Python ≥ 3.10**
* The official MCP SDKs already declared in Langflow's `pyproject.toml`:
  * `mcp>=1.6.0`  (Python)
  * `@modelcontextprotocol/sdk`  (TypeScript/Node)
* From this directory install the Node deps once:

```bash
npm install
```

## Starting the servers

### Streamable-HTTP + HTTP + SSE (same binary)

```bash
node mcp_sse_reference.js 8000
```
This binds `http://localhost:8000/mcp`  and  `http://localhost:8000/sse` plus helper endpoints `/health` and `/debug`.

### STDIO server

```bash
node mcp_stdio_reference.js   # listens on stdin/stdout
```
Typically you won't run this manually; the client will spawn it.

## Running the Python client

### Streamable-HTTP
```bash
uv run python demo_mcp_client.py --protocol=streamable-http --url=http://localhost:8000/mcp
```

### HTTP + SSE
```bash
uv run python demo_mcp_client.py --protocol=http+sse --url=http://localhost:8000/sse
```

### STDIO (client spawns server)
```bash
uv run python demo_mcp_client.py \
  --protocol=stdio \
  node mcp_stdio_reference.js
```

The client prints:
* the negotiated transport
* initialization success
* the tool list
* the result of an `echo` call

## Extending

* Add new tools in **one place** (`tools` section inside the servers) and they will be instantly available via any transport.
* The Python client auto-detects tool-list response structures across SDK versions.

---
Happy testing! :rocket: 