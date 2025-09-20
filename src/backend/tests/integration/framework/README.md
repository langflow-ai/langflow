# Langflow Integration Test Framework

Simple templates and generators for creating integration tests that follow Langflow's existing patterns.

## Quick Start

### Generate Tests

```bash
cd src/backend

# Basic component test (inputs, outputs)
python -m tests.integration.framework.generator component "ChatInput" --template basic -o test_my_component.py

# Helper component test (with ComponentInputHandle)
python -m tests.integration.framework.generator component "ParseJSONData" --template helper --module-path processing -o test_helper.py

# API component test (with API keys)
python -m tests.integration.framework.generator component "OpenAI" --template api --module-path models -o test_api.py

# Agent component test (with error handling)
python -m tests.integration.framework.generator component "MCPTools" --template agent --module-path agents -o test_agent.py

# Processing component test (simple processing)
python -m tests.integration.framework.generator component "Prompt" --template processing --module-path processing -o test_processing.py

# Flow test
python -m tests.integration.framework.generator flow "MyFlow" -o test_flow.py
```

### Manual Templates

Copy and customize these templates:

#### Component Test Template

```python
"""Integration tests for MyComponent."""

from langflow.components.my_module import MyComponent
from langflow.schema.message import Message

from tests.integration.utils import pyleak_marker, run_single_component

# Add memory leak detection
pytestmark = pyleak_marker()

async def test_default():
    """Test component with default inputs."""
    outputs = await run_single_component(MyComponent, run_input="hello")
    assert isinstance(outputs["message"], Message)
    assert outputs["message"].text == "hello"

async def test_with_inputs():
    """Test component with custom inputs."""
    outputs = await run_single_component(
        MyComponent,
        inputs={"param": "value"},
        run_input="test"
    )
    assert outputs is not None
```

#### Flow Test Template

```python
"""Integration tests for MyFlow."""

from langflow.components.input_output import ChatInput, ChatOutput
from langflow.graph import Graph
from langflow.schema.message import Message

from tests.integration.utils import pyleak_marker, run_flow

pytestmark = pyleak_marker()

async def test_simple_flow():
    """Test basic flow."""
    graph = Graph()
    input_comp = graph.add_component(ChatInput())
    output_comp = graph.add_component(ChatOutput())
    graph.add_component_edge(input_comp, ("message", "input_value"), output_comp)

    outputs = await run_flow(graph, run_input="test")
    assert isinstance(outputs["message"], Message)
```

## Template Types

### 1. Basic Component (`--template basic`)
For simple components like ChatInput, ChatOutput, TextInput:
- Uses `run_single_component()`
- Tests with run_input and custom inputs
- Good for inputs, outputs, basic processing

### 2. Helper Component (`--template helper`)
For components using `ComponentInputHandle` like ParseJSONData:
- Tests with Data and Message inputs via ComponentInputHandle
- Uses mock components and TextToData
- Good for helpers, parsers, data processors

### 3. API Component (`--template api`)
For components needing API keys like OpenAI, Anthropic:
- Includes API key testing with skip conditions
- Tests both success and failure cases
- Good for models, external services

### 4. Agent Component (`--template agent`)
For agent components like MCPTools:
- Includes error handling and exception testing
- Tests incomplete inputs with expected failures
- Good for agents, complex components

### 5. Processing Component (`--template processing`)
For simple processing like PromptComponent:
- Focused on input/output transformation
- Tests template processing and variable substitution
- Good for prompts, simple transformers

## Framework Files

- **`generator.py`** - Command-line test generator with template options
- **`templates.py`** - All template definitions for different component types

## Key Pattern

Follow existing integration tests in `/components` and `/flows`:

1. **Simple async functions** (not classes)
2. **Use `run_single_component()` and `run_flow()`**
3. **Add `pytestmark = pyleak_marker()`**
4. **Direct assertions on outputs**
5. **No complex setup/teardown**

## Running Tests

```bash
# Run component test
cd src/backend
PYTHONPATH=src/backend/base:src/backend uv run python -m pytest tests/integration/components/inputs/test_chat_input.py -v

# Run flow test
uv run python -m pytest tests/integration/flows/test_basic_prompting.py -v
```

## Component Categories Guide

| Component Type | Template | Module Path | Examples |
|---|---|---|---|
| **Input/Output** | `basic` | `input_output` | ChatInput, ChatOutput, TextInput |
| **Helpers** | `helper` | `processing` | ParseJSONData, SplitText |
| **Models** | `api` | `models` | OpenAI, Anthropic, Ollama |
| **Agents** | `agent` | `agents` | MCPTools, CrewAI |
| **Processing** | `processing` | `processing` | PromptComponent |
| **Vector Stores** | `api` | `vectorstores` | AstraDB, Pinecone |
| **Outputs** | `basic` | `outputs` | TextOutput |

## Tips

1. **Use the right template** for your component type
2. **Copy existing tests** from `/components` as references
3. **First run is slow** (~2 min) due to database setup - this is normal
4. **Use existing utilities** from `tests.integration.utils`
5. **Follow the simple pattern** - no complex frameworks needed
6. **Check imports** - adjust module paths based on your component location