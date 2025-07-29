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

```bash
uv run lfx serve my_flow.json --port 8000
```

This creates a FastAPI server with your flow available at `/flows/{flow_id}/run`.

**Options:**

- `--host, -h`: Host to bind server (default: 127.0.0.1)
- `--port, -p`: Port to bind server (default: 8000)
- `--verbose, -v`: Show diagnostic output
- `--env-file`: Path to .env file

**Example:**

```bash
# Start server (set LANGFLOW_API_KEY=your_key first)
uv run lfx serve chatbot.json --host 0.0.0.0 --port 8000

# Call API
curl -X POST http://localhost:8000/flows/{flow_id}/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: your_api_key" \
  -d '{"input_value": "Hello, world!"}'
```

### `lfx run` - Run flows directly

Execute a Langflow workflow and get results immediately.

```bash
uv run lfx run my_flow.json "What is AI?"
```

**Options:**

- `--format, -f`: Output format (json, text, message, result)
- `--verbose`: Show diagnostic output

**Examples:**

```bash
# Basic execution
uv run lfx run chatbot.json "Tell me a joke"

# JSON output
uv run lfx run data_processor.json "input text" --format json

# From stdin
echo '{"nodes": [...]}' | uv run lfx run --stdin
```

## Input Sources

Both commands support multiple input sources:

- **File path**: `uv run lfx serve my_flow.json`
- **Inline JSON**: `uv run lfx serve --flow-json '{"nodes": [...]}'`
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
