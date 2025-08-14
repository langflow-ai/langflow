# lfx - Langflow Executor

lfx is a command-line tool for running Langflow workflows. It provides two main commands: `serve` and `run`.

## Installation

### From PyPI (recommended)

```bash
# Install globally
uv pip install lfx

# Or run without installing using uvx
uvx lfx serve my_flow.json
uvx lfx run my_flow.json "input"
```

### From source (development)

```bash
# Clone and run in workspace
git clone https://github.com/langflow-ai/langflow
cd langflow/src/lfx
uv run lfx serve my_flow.json
```

## Commands

### `lfx serve` - Run flows as an API

Serve a Langflow workflow as a REST API.

**Important:** You must set the `LANGFLOW_API_KEY` environment variable before running the serve command.

```bash
export LANGFLOW_API_KEY=your-secret-key
uv run lfx serve my_flow.json --port 8000
```

This creates a FastAPI server with your flow available at `/flows/{flow_id}/run`. The actual flow ID will be displayed when the server starts.

**Options:**

- `--host, -h`: Host to bind server (default: 127.0.0.1)
- `--port, -p`: Port to bind server (default: 8000)
- `--verbose, -v`: Show diagnostic output
- `--env-file`: Path to .env file
- `--log-level`: Set logging level (debug, info, warning, error, critical)
- `--check-variables/--no-check-variables`: Check global variables for environment compatibility (default: check)

**Example:**

```bash
# Set API key (required)
export LANGFLOW_API_KEY=your-secret-key

# Start server
uv run lfx serve simple_chat.json --host 0.0.0.0 --port 8000

# The server will display the flow ID, e.g.:
# Flow ID: af9edd65-6393-58e2-9ae5-d5f012e714f4

# Call API using the displayed flow ID
curl -X POST http://localhost:8000/flows/af9edd65-6393-58e2-9ae5-d5f012e714f4/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-key" \
  -d '{"input_value": "Hello, world!"}'
```

### `lfx run` - Run flows directly

Execute a Langflow workflow and get results immediately.

```bash
uv run lfx run my_flow.json "What is AI?"
```

**Options:**

- `--format, -f`: Output format (json, text, message, result) (default: json)
- `--verbose`: Show diagnostic output
- `--input-value`: Input value to pass to the graph (alternative to positional argument)
- `--flow-json`: Inline JSON flow content as a string
- `--stdin`: Read JSON flow from stdin
- `--check-variables/--no-check-variables`: Check global variables for environment compatibility (default: check)

**Examples:**

```bash
# Basic execution
uv run lfx run simple_chat.json "Tell me a joke"

# JSON output (default)
uv run lfx run simple_chat.json "input text" --format json

# Text output only
uv run lfx run simple_chat.json "Hello" --format text

# Using --input-value flag
uv run lfx run simple_chat.json --input-value "Hello world"

# From stdin (requires --input-value for input)
echo '{"data": {"nodes": [...], "edges": [...]}}' | uv run lfx run --stdin --input-value "Your message"

# Inline JSON
uv run lfx run --flow-json '{"data": {"nodes": [...], "edges": [...]}}' --input-value "Test"
```

## Input Sources

Both commands support multiple input sources:

- **File path**: `uv run lfx serve my_flow.json`
- **Inline JSON**: `uv run lfx serve --flow-json '{"data": {"nodes": [...], "edges": [...]}}'`
- **Stdin**: `uv run lfx serve --stdin`

## Development

```bash
# Install development dependencies
make dev

# Run tests
make test

# Format code
make format
```

## License

MIT License. See [LICENSE](../../LICENSE) for details.
