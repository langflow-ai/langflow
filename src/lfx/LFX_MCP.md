# LFX MCP Server

`lfx-mcp` is an MCP (Model Context Protocol) server that gives any MCP-compatible client full programmatic control over a Langflow instance to build and run flows.

The server is implemented in `src/lfx/src/lfx/mcp/` using [FastMCP](https://github.com/jlowin/fastmcp).
It connects to Langflow's REST API.
Flow data is never cached server-side, so every mutating tool does a GET → modify → PATCH cycle.
The component registry is cached on first access per session.

## Prerequisites

- A running Langflow instance
- A Langflow API key
- `lfx` installed (`uv pip install lfx`), **or** `uv` installed if you want to run via `uvx` without a permanent install

## Connect a client

`lfx-mcp` runs over **stdio**: your MCP client spawns it as a subprocess and communicates over stdin and stdout. There is no HTTP port to connect to.

Any client that supports stdio MCP servers can connect to the `lfx-mcp` server.
Set the command to `lfx-mcp` (or `uvx lfx-mcp`) and pass the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFLOW_SERVER_URL` | URL of your Langflow instance | `http://localhost:7860` |
| `LANGFLOW_API_KEY` | API key for authentication | — |

For example, to connect to Claude Desktop, add the following to the Claude Desktop configuration file at `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "langflow": {
      "command": "lfx-mcp",
      "env": {
        "LANGFLOW_SERVER_URL": "http://localhost:7860",
        "LANGFLOW_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

If `lfx` is not installed globally, use it through `uvx` instead.

```json
{
  "mcpServers": {
    "langflow": {
      "command": "uvx",
      "args": ["lfx-mcp"],
      "env": {
        "LANGFLOW_SERVER_URL": "http://localhost:7860",
        "LANGFLOW_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

## Server tools

The server exposes the following tool groups to the connected MCP client.

### Auth

| Tool | Description |
|------|-------------|
| `login` | Authenticate with a Langflow server using username and password. Not needed if `LANGFLOW_API_KEY` is set. |

### Flows

| Tool | Description |
|------|-------------|
| `create_flow` | Create a new empty flow |
| `create_flow_from_spec` | Create a complete flow from a compact text spec (nodes, edges, config in one call) |
| `list_flows` | List flows on the server, with ASCII graph diagrams |
| `get_flow_info` | Get detailed info about a flow: components, connections, graph |
| `delete_flow` | Delete a flow |
| `duplicate_flow` | Copy an existing flow |
| `rename_flow` | Update a flow's name or description |
| `update_flow_from_spec` | Replace an existing flow's nodes, edges, and config from a spec |
| `export_flow` | Export a flow as JSON with sensitive fields redacted |

### Starter projects

| Tool | Description |
|------|-------------|
| `list_starter_projects` | List Langflow's built-in example flows |
| `use_starter_project` | Create a new flow from a starter project template |

### Components

| Tool | Description |
|------|-------------|
| `search_component_types` | Find component types by name, category, or output type |
| `describe_component_type` | Get a component type's inputs, outputs, fields, and advanced fields |
| `components` | Search or describe component types in one call |
| `add_component` | Add a component to a flow |
| `remove_component` | Remove a component and its connections from a flow |
| `configure_component` | Set parameter values on a component |
| `list_components` | List all components in a flow |
| `get_component_info` | Get a component's current parameter values (sensitive fields redacted) |
| `freeze_component` | Freeze a component so it uses cached output and skips re-execution |
| `unfreeze_component` | Unfreeze a component so it re-executes on the next run |

### Connections

| Tool | Description |
|------|-------------|
| `connect_components` | Connect an output of one component to an input of another |
| `disconnect_components` | Remove connections between two components |

### Execution

| Tool | Description |
|------|-------------|
| `run_flow` | Run a flow and return the output; streams progress events when the client supports it |
| `build_flow` | Trigger a server-side build to validate components and connections |
| `validate_flow` | Validate a flow and return structured per-component results |
| `get_build_results` | Get per-component build results from the last run |
| `get_component_output` | Get a specific component's output from the last run |

### Utility

| Tool | Description |
|------|-------------|
| `layout_flow` | Re-layout a flow's components using the Sugiyama algorithm |
| `notify_done` | Signal that you are done modifying a flow so the UI updates immediately |
| `batch` | Execute multiple actions in sequence; use `$N.field` to reference results from previous steps |

## How to use the server

The server's instructions describe the intended usage pattern:

1. Authenticate — call `login`, or set `LANGFLOW_API_KEY` before starting
2. Discover components — use `search_component_types` or `describe_component_type`
3. Build a flow — use `create_flow_from_spec` for a complete flow in one call, or step-by-step with `create_flow` → `add_component` → `configure_component` → `connect_components`
4. Run the flow — call `run_flow`

The `batch` tool lets you send multiple actions in a single call, with `$N.field` references to chain results:

```json
[
  {"tool": "create_flow", "args": {"name": "My Chatbot"}},
  {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "ChatInput"}},
  {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "OpenAIModel"}},
  {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "ChatOutput"}},
  {"tool": "connect_components", "args": {
    "flow_id": "$0.id", "source_id": "$1.id", "source_output": "message",
    "target_id": "$2.id", "target_input": "input_value"
  }},
  {"tool": "connect_components", "args": {
    "flow_id": "$0.id", "source_id": "$2.id", "source_output": "text_output",
    "target_id": "$3.id", "target_input": "input_value"
  }}
]
```