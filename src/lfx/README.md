# LFX - Langflow Executor

The Langflow Executor (LFX) is a command-line tool that serves and runs flows statelessly from flow JSON files with minimal dependencies.

Running a flow with LFX is similar to running flows with the `--backend-only` environment variable enabled, but even more lightweight because the Langflow package and all of its dependencies don't need to be installed.

LFX uses a no-op database interface called [`NoopSession`](https://github.com/langflow-ai/langflow/blob/main/src/lfx/src/lfx/services/session.py) for all operations that require persistent state.
There is no `langflow.db` database file when using LFX.
You can run flows with the API, but any stateful operations that depend on the Langflow database, like saving flows, storing messages, or managing users **will not** persist data.
Operations that depend on `langflow.db` will not work as they do in the full Langflow application.

LFX includes two commands for executing flows:

- **`lfx serve`**: Starts a FastAPI server hosting a Langflow API endpoint with your flow available at `/flows/{flow_id}/run`. The flow graph is stored in memory at all times, so there is less overhead for loading the graph from a database.
- **`lfx run`**: Executes a flow locally and returns the results to `stdout`.

## Prerequisites

- Install [Python](https://www.python.org/downloads/release/python-3100/).
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Create or download a flow JSON file. For example, download the Simple Agent flow from the repository:

  ```bash
  curl -o simple-agent-flow.json "https://raw.githubusercontent.com/langflow-ai/langflow/main/src/backend/base/langflow/initial_setup/starter_projects/Simple%20Agent.json"
  ```

- Create an [OpenAI API key](https://platform.openai.com/api-keys).
- Create a Langflow API key. For LFX, you can generate a secure token locally (see [Serve the simple agent starter flow with `lfx serve`](#serve-the-simple-agent-starter-flow-with-lfx-serve)), or create one through the Langflow server UI or CLI.

## Install LFX

LFX can be installed in multiple ways. If you have installed Langflow OSS version >=1.6, `lfx` is already included.

### Clone repository

1. Clone the Langflow repository:

   ```bash
   git clone https://github.com/langflow-ai/langflow
   ```

2. Change directory to `langflow/src/lfx`:

   ```bash
   cd langflow/src/lfx
   ```

   From this directory, you can run `lfx` commands using `uv run lfx` as shown in [lfx serve](#serve-the-simple-agent-starter-flow-with-lfx-serve) or [lfx run](#run-the-simple-agent-flow-with-lfx-run).

### Install from PyPI

1. Create and activate a virtual environment:

   ```bash
   uv venv lfx-venv
   source lfx-venv/bin/activate
   ```

2. Install the LFX package from PyPI:

   ```bash
   uv pip install lfx
   ```

   To install the latest nightly version of LFX:

   ```bash
   uv pip install lfx-nightly
   ```

   To run `lfx` commands, continue to [lfx serve](#serve-the-simple-agent-starter-flow-with-lfx-serve) or [lfx run](#run-the-simple-agent-flow-with-lfx-run).

### Run without installing

Run LFX without installing it locally using `uvx`.

1. Create a Langflow API key (see [Serve](#serve-the-simple-agent-starter-flow-with-lfx-serve)), and set `LANGFLOW_API_KEY` in the same terminal session as `lfx`:

   ```bash
   export LANGFLOW_API_KEY="sk..."
   ```

2. Run `lfx serve` using `uvx`:

   ```bash
   uvx lfx serve simple-agent-flow.json
   ```

   This command downloads and runs LFX in a temporary environment without permanent installation. From the same environment, you can also run flows directly with [lfx run](#run-the-simple-agent-flow-with-lfx-run).

## Serve the simple agent starter flow with `lfx serve`

To serve a flow as a REST API endpoint, set a `LANGFLOW_API_KEY` and run the flow JSON.

The API key is required for security because `lfx serve` can create a publicly accessible FastAPI server.

This example uses the **Agent** component's built-in OpenAI model, which requires an OpenAI API key. If you want to use a different provider, edit the model provider, model name, and credentials accordingly.

1. Generate a Langflow API key.

   For LFX, you can generate a secure token locally to use as your `LANGFLOW_API_KEY`:

   ```bash
   uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   This is different from creating a Langflow API key through the Langflow server UI or CLI, which stores the key in the Langflow database. For LFX, you only need a secure token string to authenticate requests to your LFX server.

2. Set up your environment variables using one of the following options.

   **Option: .env file**

   Create a `.env` file and populate it with your flow's variables. The `LANGFLOW_API_KEY` is required. This example assumes the flow requires an OpenAI API key.

   ```bash
   LANGFLOW_API_KEY="sk..."
   OPENAI_API_KEY="sk-..."
   ```

   **Option: Export variables**

   Export your variables in the same terminal session where you'll start the server. You must declare your variables before the server starts for the server to pick them up.

   ```bash
   export LANGFLOW_API_KEY="sk..."
   export OPENAI_API_KEY="sk-..."
   ```

3. Install dependencies.

   If you already have Langflow installed, or if you're running from source at `src/lfx`, LFX is included with Langflow and all dependencies are already available. You don't need to install additional dependencies.

   If you install the standalone `lfx` package from [PyPI](https://pypi.org/project/lfx/) or run LFX with `uvx`, you need to manually install the dependencies required by the components in your flow.

   To find which dependencies your flow requires:

   1. Run your flow with [lfx run](#run-the-simple-agent-flow-with-lfx-run):

      ```bash
      uv run lfx run simple-agent-flow.json "test input"
      ```

      LFX reports any missing dependencies in the subsequent error message.
   2. Install the missing dependencies that LFX reports.

   For example, to run the simple agent template flow, install these dependencies in your environment before running the simple agent flow:

   ```bash
   uv pip install "langchain~=0.3.23" "langchain-core<1.0.0" "langchain-community" "langchain-openai" "langchain-text-splitters" beautifulsoup4 lxml requests
   ```

4. Start the server with your variable values using one of the following options.

   **Option: .env file**

   This example assumes your flow file and `.env` file are in the current directory:

   ```bash
   uv run lfx serve simple-agent-flow.json --env-file .env
   ```

   If your `.env` file is in a different location, provide the full or relative path:

   ```bash
   uv run lfx serve simple-agent-flow.json --env-file /path/to/.env
   ```

   **Option: Export variables**

   If you exported your variables, the command to start the server automatically picks up the values when it starts:

   ```bash
   uv run lfx serve simple-agent-flow.json
   ```

   To export new values, stop the server, export the variables, and then start the server again.

5. The startup process displays a `flow_id` value in the output. Copy the `flow_id` to use in the test API call in the next step. In this example, the `flow_id` is `c1dab29d-3364-58ef-8fef-99311d32ee42`:

   ```
    ╭───────────────────────────── LFX Server ─────────────────────────────╮
    │ 🎯 Single Flow Served Successfully!                                  │
    │                                                                      │
    │ Source: /Users/mendonkissling/Downloads/simple-agent-flow.json       │
    │ Server: http://127.0.0.1:8000                                        │
    │ API Key: sk-...                                                      │
    │                                                                      │
    │ Send POST requests to:                                               │
    │ http://127.0.0.1:8000/flows/c1dab29d-3364-58ef-8fef-99311d32ee42/run │
    │                                                                      │
    │ With headers:                                                        │
    │ x-api-key: sk-...                                                    │
    │                                                                      │
    │ Or query parameter:                                                  │
    │ ?x-api-key=sk-...                                                    │
    │                                                                      │
    │ Request body:                                                        │
    │ {'input_value': 'Your input message'}                                │
    ╰──────────────────────────────────────────────────────────────────────╯
   ```

6. To send a test request to the server, open a new terminal and export your `flow_id` and Langflow API key values as variables:

   ```bash
   export LANGFLOW_API_KEY="sk..."
   export FLOW_ID="c1dab29d-3364-58ef-8fef-99311d32ee42"
   ```

7. Test the server with an API call to the `/flows/flow_id/run` endpoint:

   ```bash
   curl -X POST http://localhost:8000/flows/$FLOW_ID/run \
     -H "Content-Type: application/json" \
     -H "x-api-key: $LANGFLOW_API_KEY" \
     -d '{"input_value": "Hello, world!"}'
   ```

   Successful response example:

   ```json
   {
     "result": "Hello world! 👋\n\nHow can I help you today? If you have any questions or need assistance, just let me know!",
     "success": true,
     "logs": "\n\n\u001b[1m> Entering new None chain...\u001b[0m\n\u001b[32;1m\u001b[1;3mHello world! 👋\n\nHow can I help you today?...\u001b[0m\n\n\u001b[1m> Finished chain.\u001b[0m\n",
     "type": "message",
     "component": "Chat Output"
   }
   ```

Your flow is now running as a lightweight API endpoint, with only the flow's required dependencies and no visual builder installed. Users who call your endpoint don't need to install Langflow or configure their own LLM provider keys.

To make your server publicly accessible, use a tunneling service like ngrok or deploy to a public cloud provider.

### LFX response schema

The LFX server's response schema is different from the Langflow API `/run` endpoint's schema. Requests to the LFX server's `/flows/{flow_id}/run` endpoint return the following fields:

```json
{
  "result": "string",      // Output result from the flow execution
  "success": true,         // Whether execution was successful
  "logs": "string",        // Captured logs from execution
  "type": "message",       // Type of result
  "component": "string"    // The component that generated the result (e.g. "Chat Output")
}
```

To view the LFX server's API docs and schema, see the `/docs` endpoint at `http://localhost:8000/docs`.

### LFX serve options

| Option | Description |
|--------|--------------|
| `--check-variables` / `--no-check-variables` | Check global variables for environment compatibility. Default: `--check-variables`. |
| `--env-file` | Path to the `.env` file containing environment variables. |
| `--host`, `-h` | Host to bind the server to. Default: `127.0.0.1`. |
| `--log-level` | Logging level. One of: `debug`, `info`, `warning`, `error`, `critical`. Default: `warning`. |
| `--port`, `-p` | Port to bind the server to. Default: `8000`. |
| `--verbose`, `-v` | Show diagnostic output and execution details. |
| `--flow-json` | Read inline flow JSON content as a string. Example: `uv run lfx serve --flow-json '{...}'`. |
| `--stdin` | Read JSON flow content from `stdin`. Example: `cat flow.json | uv run lfx serve --stdin`. |

## Run the simple agent flow with `lfx run`

The `lfx run` command runs a flow from a JSON file without serving it, and the output is sent to `stdout`. Input to `lfx run` can be a path to the JSON file, inline JSON passed with `--input-value`, or read from `stdin`. No Langflow API key is required.

This example uses the **Agent** component's built-in OpenAI model, which requires an OpenAI API key. If you want to use a different provider, edit the model provider, model name, and credentials accordingly.

1. Export your variables in the same terminal session where you'll run the flow:

   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. Install dependencies.

   If you already have Langflow installed, or if you're running from source at `src/lfx`, LFX is included with Langflow and all dependencies are already available. You don't need to install additional dependencies.

   If you install the standalone `lfx` package from [PyPI](https://pypi.org/project/lfx/) or run LFX with `uvx`, you need to manually install the dependencies required by the components in your flow.

   To find which dependencies your flow requires:

   1. Run your flow with [lfx run](#run-the-simple-agent-flow-with-lfx-run):

      ```bash
      uv run lfx run simple-agent-flow.json "test input"
      ```

      LFX reports any missing dependencies in the subsequent error message.
   2. Install the missing dependencies that LFX reports.

   For example, to run the simple agent template flow, install these dependencies in your environment before running the simple agent flow:

   ```bash
   uv pip install "langchain~=0.3.23" "langchain-core<1.0.0" "langchain-community" "langchain-openai" "langchain-text-splitters" beautifulsoup4 lxml requests
   ```

3. Run the flow from a flow JSON file:

   ```bash
   uv run lfx run simple-agent-flow.json "Hello world"
   ```

   This flow expects a `Message` input, which is a simple text string.

   You can also use the `--input-value` flag instead of a positional argument:

   ```bash
   uv run lfx run simple-agent-flow.json --input-value "Hello world"
   ```

   The `--input-value` flag is required when using `--stdin` or `--flow-json` options, since those options use the positional argument for the flow definition instead of the input value.

In addition to running flows from JSON files, `lfx run` supports other input methods, described below.

### Run flows from stdin

The `--stdin` option lets you run flows from dynamic sources (APIs, databases) or after modifying a flow before execution. The command reads the flow's JSON definition from `stdin`, validates the JSON structure, and runs the flow. The `--input-value` flag is required when using `--stdin`.

Read a flow JSON from stdin:

```bash
cat simple-agent-flow.json | uv run lfx run --stdin \
  --input-value "Hello world" \
  --format json | jq '.result'
```

Fetch a flow JSON from a remote API and run it:

```bash
curl https://api.example.com/flows/my-agent-flow | uv run lfx run --stdin \
  --input-value "Hello world"
```

Modify a flow created in the visual builder before execution (e.g. change the OpenAI model to `gpt-4o`):

```bash
cat simple-agent-flow.json | jq '(.data.nodes[] | select(.data.node.template.model_name.value) | .data.node.template.model_name.value) = "gpt-4o"' | \
  uv run lfx run --stdin \
  --input-value "Hello world" \
  --format json | jq '.result'
```

### Run flows with inline JSON

Instead of piping from `stdin` or reading from a JSON file, you can pass the flow JSON directly as a string argument. The `--input-value` flag is required when using `--flow-json`.

```bash
uv run lfx run --flow-json '{"data": {"nodes": [...], "edges": [...]}}' \
  --input-value "Hello world"
```

### LFX run options

| Option | Description |
|--------|--------------|
| `--check-variables` / `--no-check-variables` | Validate the flow's global variables. Default: check. |
| `--flow-json` | Load inline JSON flow content as a string. |
| `--format`, `-f` | Output format. One of: `json`, `text`, `message`, `result`. Default: `json`. |
| `--input-value` | Input value to pass to the graph. |
| `--stdin` | Read JSON flow content from `stdin`. |
| `--timing` | Include detailed timing information in output. |
| `--verbose`, `-v` | Show basic progress and diagnostic output. |
| `-vv` | Show detailed progress and debug information. |
| `-vvv` | Show full debugging output including component logs. |

In addition to running flows from JSON files, you can use `lfx run` with Python scripts that define flows programmatically. This approach allows you to create flows directly in Python code without the visual builder.

For a complete example of creating an agent flow programmatically using LFX components, see the [Complete Agent Example on PyPI](https://pypi.org/project/lfx) or the **Complete Agent Example** below.

#### Complete agent example

Create a file called `simple_agent.py`:

```python
"""A simple agent flow example for Langflow.

Usage:
    uv run lfx run simple_agent.py "How are you?"
"""

import os
from pathlib import Path

from lfx import components as cp
from lfx.graph import Graph
from lfx.log.logger import LogConfig


async def get_graph() -> Graph:
    """Create and return the graph with async component initialization."""
    log_config = LogConfig(
        log_level="INFO",
        log_file=Path("langflow.log"),
    )

    chat_input = cp.ChatInput()
    agent = cp.AgentComponent()
    url_component = cp.URLComponent()
    tools = await url_component.to_toolkit()

    agent.set(
        model_name="gpt-4.1-mini",
        agent_llm="OpenAI",
        api_key=os.getenv("OPENAI_API_KEY"),
        input_value=chat_input.message_response,
        tools=tools,
    )
    chat_output = cp.ChatOutput().set(input_value=agent.message_response)

    return Graph(chat_input, chat_output, log_config=log_config)
```

Install dependencies and set your OpenAI API key, then run:

```bash
uv run lfx run simple_agent.py "How are you?" --verbose
```

## Development

```bash
# Install development dependencies
make dev

# Run tests
make test

# Format code
make format
```

## Pluggable services

LFX supports a pluggable service architecture that lets you customize and extend its behavior. You can replace built-in services (storage, telemetry, tracing, etc.) with your own implementations or use Langflow's full-featured services.

For more information, see [PLUGGABLE_SERVICES.md](./PLUGGABLE_SERVICES.md).

## Flattened component access

LFX supports simplified component imports for a better developer experience when building flows in Python.
You get simpler imports, easier discovery via `cp.ComponentName`, and full backward compatibility with the traditional import method.

**Before (old import style):**

```python
from lfx.components.agents.agent import AgentComponent
from lfx.components.data.url import URLComponent
from lfx.components.input_output import ChatInput, ChatOutput
```

**Now (flattened style):**

```python
from lfx import components as cp

chat_input = cp.ChatInput()
agent = cp.AgentComponent()
url_component = cp.URLComponent()
chat_output = cp.ChatOutput()
```

## Component category allowlist and blocklist

You can restrict which component categories are available when loading flows by using an allowlist or a blocklist.

### Environment variables

Both settings are optional. When unset or empty, all categories from the component index are loaded.

| Variable | Description |
|----------|-------------|
| `LANGFLOW_COMPONENT_CATEGORY_ALLOWLIST` | Comma-separated list of component category names to **include**. If empty (default), all categories are included. If set, only the listed categories are available. |
| `LANGFLOW_COMPONENT_CATEGORY_BLOCKLIST` | Comma-separated list of component category names to **exclude**. If empty (default), no categories are excluded. Applied after the allowlist. |

Category names are case-insensitive.

### Component categories

Category names in the allowlist and blocklist match the component index (e.g. top-level folders under `lfx.components`). The virtual keyword **`core`** in the allowlist or blocklist expands to the following core categories (aligned with the frontend sidebar):

- `input_output`, `data_source`, `models_and_agents`, `llm_operations`, `files_and_knowledge`, `processing`, `flow_controls`, `utilities`, `prototypes`, `tools`, `agents`, `data`, `logic`, `helpers`, `models`, `vectorstores`, `inputs`, `outputs`, `prompts`, `chains`, `documentloaders`, `link_extractors`, `output_parsers`, `retrievers`, `textsplitters`, `toolkits`

Provider-specific and other categories (e.g. `openai`, `anthropic`, `google`, `langchain_utilities`) are also valid; the full set depends on your LFX version and index.

### How to use in LFX

1. Set one or both environment variables before running `lfx serve` or `lfx run`. The filter is applied when the component index is loaded.

Allowlist only — restrict to specific categories:

   ```bash
   export LANGFLOW_COMPONENT_CATEGORY_ALLOWLIST="openai,anthropic,google,processing,input_output"
   uv run lfx serve my_flow.json
   ```

Blocklist only — load all categories except the ones you exclude:

   ```bash
   export LANGFLOW_COMPONENT_CATEGORY_BLOCKLIST="prototypes,langchain_utilities"
   uv run lfx run my_flow.json "Hello"
   ```

Virtual `core` keyword — use `core` in the allowlist or blocklist to refer to all core categories at once (e.g. allow only core categories, or exclude all core from a broader set):

   ```bash
   export LANGFLOW_COMPONENT_CATEGORY_ALLOWLIST="core"
   uv run lfx serve my_flow.json
   ```

## License

MIT License. See [LICENSE](../../LICENSE) for details.
