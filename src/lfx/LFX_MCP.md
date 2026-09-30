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
Set the command to `lfx-mcp` (or `uvx --from lfx lfx-mcp`) and pass the following environment variables:

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
      "args": ["--from", "lfx", "lfx-mcp"],
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
| `configure_component` | Set parameter values on a component. Returns a `warnings` field if a server-side refresh failed for a parameter, such an API key not yet configured on the component. |
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
| `run_flow` | Run a flow and return the output; streams progress events when the client supports it. Accepts `input_type` (default: `"chat"`), `output_type` (default: `"chat"`), and `tweaks` (dict of component param overrides at runtime, e.g. `{"MyComponent": {"temperature": 0.2}}`). |
| `build_flow` | Trigger a server-side build to validate components and connections (async, returns `job_id`; poll separately for results) |
| `validate_flow` | Validate a flow inline; fast-fails on the first component error and returns the structured result (blocks until done, unlike `build_flow`) |
| `get_build_results` | Get per-component build results from the last run |
| `get_component_output` | Get a specific component's output from the last run |

### Utility

| Tool | Description |
|------|-------------|
| `layout_flow` | Re-layout a flow's components using the Sugiyama algorithm |
| `notify_done` | Signal that you are done modifying a flow so the UI updates immediately. Optional `summary` string is forwarded in the `flow_settled` event payload visible in the UI (e.g. `"Built a RAG pipeline with OpenAI and Pinecone"`). |
| `batch` | Execute multiple actions in sequence; use `$N.field` to reference results from previous steps. Cannot nest `batch` inside another `batch` (excluded from its own tool map). |

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

## Quickstart: build and run a flow with Claude Code

This example shows how to connect Claude Code to a running Langflow instance using `lfx-mcp`, then build, validate, and run a chatbot flow from your terminal.

### Prerequisites

- A Langflow server running at `http://localhost:7860`
- A Langflow API key. Create one in the Langflow UI under **Settings → Langflow API → Create new API key**.
- An OpenAI API key. This example uses Langflow's Agent component with OpenAI. Add your OpenAI API key as a Global Variable in Langflow under **Settings → Global Variables** so all flows can use it automatically, or pass it explicitly when prompted. If you prefer a different provider, adjust the prompt accordingly.
- `uv` installed. The `uvx` command used to run `lfx-mcp` requires `uv`. For more information, see the [uv docs](https://docs.astral.sh/uv/getting-started/installation/).
- Claude Code installed. For more information, see the [Claude Code docs](https://docs.anthropic.com/en/docs/claude-code).

1. Add `lfx-mcp` to Claude Code.

Run the following command in your terminal.
Replacing the placeholder values with your actual keys:

```bash
claude mcp add langflow \
  -e LANGFLOW_SERVER_URL=http://localhost:7860 \
  -e LANGFLOW_API_KEY=<YOUR_LANGFLOW_API_KEY> \
  -- uvx --from lfx lfx-mcp
```

2. Verify `lfx-mcp` was added to Claude Code:

```bash
claude mcp list
```

The output should include:

```
langflow: uvx --from lfx lfx-mcp
```

This confirms that Claude Code knows to spawn an `lfx-mcp` process when it needs to talk to Langflow.

3. Start Claude Code in your terminal:

```bash
claude
```

4. Give Claude Code instructions.
For example:

```
Create a simple agent chatbot flow in Langflow using OpenAI, validate the flow, and then run it with the message "What is Langflow?"
```

Given this instruction, Claude Code will typically do the following:

    1. Discover the available components using `search_component_types` or `describe_component_type`.
    2. Create the flow with all nodes and connections in one request using `create_flow_from_spec`.
    3. Validate that every component is correctly connected using `validate_flow`.
    4. Run the flow using `run_flow` and return the response.

The flow appears in your Langflow UI at `http://localhost:7860` because `lfx-mcp` creates it through the Langflow API. The answer is printed in your terminal:

```
Langflow is a visual workflow builder for AI-powered agents. It lets you
connect LLMs, tools, and data sources in a drag-and-drop UI, then expose
the result as an API endpoint or run it from the command line.
```

### Troubleshooting

* `lfx-mcp` not found when adding the server
Use `uvx --from lfx lfx-mcp`, not `uvx lfx-mcp`. The `lfx-mcp` binary ships inside the `lfx` package, and there is no standalone `lfx-mcp` package on PyPI.

* 403 Forbidden when Claude Code tries to use tools
The API key is invalid or expired. Create a new API key in Langflow under **Settings → Langflow API**, and then remove and re-add the MCP server:
```bash
claude mcp remove langflow
claude mcp add langflow \
  -e LANGFLOW_SERVER_URL=http://localhost:7860 \
  -e LANGFLOW_API_KEY=<YOUR_LANGFLOW_API_KEY> \
  -- uvx --from lfx lfx-mcp
```

* Flow validation fails with an LLM provider error
The API key for your LLM provider is not configured. Add it as a Global Variable in Langflow (**Settings → Global Variables → Add**), and then ask Claude Code to validate the flow again.