# Langflow Agentic Module - Backend Documentation

## Overview

The Agentic module provides an AI-powered assistant that helps users create Langflow components through natural language interaction. It executes specialized flows, validates generated Python code, and provides real-time streaming feedback during component generation.

## Architecture

```
langflow/agentic/
├── api/
│   ├── __init__.py
│   ├── router.py          # FastAPI endpoints
│   └── schemas.py         # Pydantic models for request/response
├── helpers/
│   ├── __init__.py
│   ├── code_extraction.py # Extract Python from LLM responses
│   ├── error_handling.py  # User-friendly error messages
│   ├── sse.py             # Server-Sent Events formatting
│   └── validation.py      # Component code validation
├── services/
│   ├── __init__.py
│   ├── assistant_service.py  # Main orchestration with retry logic
│   ├── flow_executor.py      # Flow execution and streaming
│   └── provider_service.py   # Model provider configuration
├── flows/
│   └── LangflowAssistant.json  # The assistant flow definition
└── GENERATE_COMPONENT.md       # Prompt template for component generation
```

## Module Responsibilities

### API Layer (`api/`)

#### `router.py`
HTTP endpoints that handle incoming requests. This is a thin layer that:
- Validates authentication (requires logged-in user)
- Retrieves API keys from user's global variables
- Delegates business logic to service modules
- Returns appropriate HTTP responses

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/agentic/execute/{flow_name}` | Execute any named flow |
| `GET` | `/agentic/check-config` | Check if assistant is properly configured |
| `POST` | `/agentic/assist` | Chat with the assistant (non-streaming) |
| `POST` | `/agentic/assist/stream` | Chat with the assistant (SSE streaming) |

#### `schemas.py`
Pydantic models for request/response validation:

```python
class AssistantRequest(BaseModel):
    flow_id: str                    # Required: Flow context
    component_id: str | None        # Optional: Component being edited
    field_name: str | None          # Optional: Field being edited
    input_value: str | None         # User's message/prompt
    max_retries: int | None         # Max validation retry attempts
    model_name: str | None          # Specific model to use
    provider: str | None            # Specific provider to use
    session_id: str | None          # Session for memory isolation

class ValidationResult(BaseModel):
    is_valid: bool                  # Whether code passed validation
    code: str | None                # The validated code
    error: str | None               # Error message if invalid
    class_name: str | None          # Extracted component class name

# Step types for SSE progress events
StepType = Literal[
    "generating",           # LLM is generating response
    "generation_complete",  # LLM finished generating
    "extracting_code",      # Extracting Python code
    "validating",           # Validating component code
    "validated",            # Validation succeeded
    "validation_failed",    # Validation failed
    "retrying",             # Retrying with error context
]
```

### Helpers Layer (`helpers/`)

Pure functions with single responsibilities. No side effects, easily testable.

#### `code_extraction.py`
Extracts Python code from LLM markdown responses.

**Key Functions:**
- `extract_python_code(text: str) -> str | None`: Main entry point
- `_find_code_blocks(text: str) -> list[str]`: Find all code blocks
- `_find_unclosed_code_block(text: str) -> list[str]`: Handle streaming cutoffs
- `_find_component_code(matches: list[str]) -> str | None`: Prioritize Component classes

**Handles Edge Cases:**
- Closed code blocks: ` ```python ... ``` `
- Unclosed blocks (streaming cutoff): ` ```python ... `
- Generic code blocks: ` ``` ... ``` `
- Multiple code blocks (prefers one with `Component` class)
- Case-insensitive language tags

#### `error_handling.py`
Converts technical API errors into user-friendly messages.

**Key Functions:**
- `extract_friendly_error(error_msg: str) -> str`: Main entry point
- `_truncate_error_message(error_msg: str) -> str`: Handle long errors

**Error Pattern Mapping:**

| Pattern Keywords | User-Friendly Message |
|------------------|----------------------|
| rate_limit, 429 | "Rate limit exceeded. Please wait..." |
| authentication, api_key, 401 | "Authentication failed. Check your API key." |
| quota, billing | "API quota exceeded. Check your billing." |
| timeout | "Request timed out. Please try again." |
| connection, network | "Connection error. Check your network." |
| 500, internal server error | "Server error. Please try again later." |
| model not found | "Model not available. Select a different model." |
| content filter/policy | "Request blocked by content policy." |

#### `sse.py`
Formats Server-Sent Events for streaming responses.

**Functions:**
```python
def format_progress_event(
    step: StepType,
    attempt: int,
    max_attempts: int,
    *,
    message: str | None = None,
    error: str | None = None,
    class_name: str | None = None,
    component_code: str | None = None,
) -> str

def format_complete_event(data: dict) -> str
def format_error_event(message: str) -> str
def format_token_event(chunk: str) -> str
```

**SSE Format:**
```
data: {"event": "progress", "step": "generating", "attempt": 1, "max_attempts": 4}\n\n
data: {"event": "token", "chunk": "Hello"}\n\n
data: {"event": "complete", "data": {...}}\n\n
data: {"event": "error", "message": "..."}\n\n
```

#### `validation.py`
Validates that generated code is a valid Langflow component.

**Key Functions:**
- `validate_component_code(code: str) -> ValidationResult`: Main entry point
- `_safe_extract_class_name(code: str) -> str | None`: Extract class name with fallback
- `_extract_class_name_regex(code: str) -> str | None`: Regex fallback for broken code

**Validation Process:**
1. Extract class name from code (with regex fallback for syntax errors)
2. Dynamically create the class using `create_class()`
3. **Instantiate the class** to trigger `__init__` validation
4. Return `ValidationResult` with success/failure details

**Why Instantiation?**
The Component base class performs validation in `__init__`, such as:
- Checking for overlapping input/output names
- Validating required fields
- Type checking

### Services Layer (`services/`)

Business logic orchestration. Handles complex workflows and state.

#### `provider_service.py`
Manages model provider configuration and API key retrieval.

**Constants:**
```python
PREFERRED_PROVIDERS = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"]

DEFAULT_MODELS = {
    "Anthropic": "claude-sonnet-4-5-20250514",
    "OpenAI": "gpt-5.2",
    "Google Generative AI": "gemini-2.0-flash",
    "Groq": "llama-3.3-70b-versatile",
}
```

**Key Functions:**
```python
async def get_enabled_providers_for_user(
    user_id: UUID | str,
    session: AsyncSession,
) -> tuple[list[str], dict[str, bool]]
# Returns (enabled_providers, provider_status_map)

async def check_api_key(
    variable_service: VariableService,
    user_id: UUID | str,
    key_name: str,
    session: AsyncSession,
) -> str | None
# Checks global variables first, then environment

def get_default_provider(enabled_providers: list[str]) -> str | None
# Returns first preferred provider that's enabled

def get_default_model(provider: str) -> str | None
# Returns default model for provider
```

#### `flow_executor.py`
Executes Langflow flows with optional model injection and streaming.

**Key Classes:**
```python
@dataclass
class FlowExecutionResult:
    result: dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None

    @property
    def has_error(self) -> bool

    @property
    def has_result(self) -> bool
```

**Key Functions:**
```python
def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str | None = None,
) -> dict
# Injects model configuration into Agent nodes

async def execute_flow_file(
    flow_filename: str,
    input_value: str | None = None,
    global_variables: dict[str, str] | None = None,
    *,
    verbose: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> dict
# Execute flow and return result

async def execute_flow_file_streaming(
    # Same parameters as above
) -> AsyncGenerator[tuple[str, Any], None]
# Execute flow with token streaming, yields ("token", chunk) and ("end", result)

def extract_response_text(result: dict) -> str
# Extract text from various result formats
```

#### `assistant_service.py`
Main orchestration service with validation and retry logic.

**Constants:**
```python
MAX_VALIDATION_RETRIES = 3
VALIDATION_UI_DELAY_SECONDS = 0.3  # Small delay for UI feedback
LANGFLOW_ASSISTANT_FLOW = "LangflowAssistant.json"

VALIDATION_RETRY_TEMPLATE = """The previous component code has an error. Please fix it.

ERROR:
{error}

BROKEN CODE:
```python
{code}
```

Please provide a corrected version of the component code."""
```

**Key Functions:**
```python
async def execute_flow_with_validation(
    flow_filename: str,
    input_value: str,
    global_variables: dict[str, str],
    *,
    max_retries: int = MAX_VALIDATION_RETRIES,
    user_id: str | None = None,
    session_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> dict
# Non-streaming execution with validation loop

async def execute_flow_with_validation_streaming(
    # Same parameters
) -> AsyncGenerator[str, None]
# Streaming execution with SSE events
```

## Data Flow

### Non-Streaming Request Flow

```
┌─────────┐    ┌──────────┐    ┌───────────────────┐    ┌──────────────┐
│ Client  │───►│ Router   │───►│ Assistant Service │───►│ Flow Executor│
└─────────┘    └──────────┘    └───────────────────┘    └──────────────┘
                                        │                       │
                                        ▼                       ▼
                               ┌─────────────────┐      ┌─────────────┐
                               │ Code Extraction │      │ LFX run_flow│
                               └─────────────────┘      └─────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │   Validation    │
                               └─────────────────┘
                                        │
                            ┌───────────┴───────────┐
                            ▼                       ▼
                       [Valid]                 [Invalid]
                            │                       │
                            ▼                       ▼
                    Return Result           Retry with Error
                                           (up to max_retries)
```

### Streaming Request Flow

```
┌─────────┐    ┌──────────┐    ┌───────────────────┐
│ Client  │◄──►│ Router   │───►│ Assistant Service │
└─────────┘    └──────────┘    └───────────────────┘
     ▲                                  │
     │                                  ▼
     │ SSE              ┌───────────────────────────────┐
     │ Events           │     Streaming Loop            │
     │                  │                               │
     │                  │  1. yield progress(generating)│
     │◄─────────────────│  2. yield token(chunk)...     │
     │◄─────────────────│  3. yield progress(complete)  │
     │◄─────────────────│  4. yield progress(validating)│
     │◄─────────────────│  5a. yield progress(validated)│
     │◄─────────────────│      yield complete(result)   │
     │                  │  OR                           │
     │◄─────────────────│  5b. yield progress(failed)   │
     │◄─────────────────│      yield progress(retrying) │
     │                  │      → back to step 1         │
     │                  └───────────────────────────────┘
```

## SSE Event Sequence

### Successful Generation (First Try)
```
data: {"event": "progress", "step": "generating", "attempt": 1, "max_attempts": 4}

data: {"event": "token", "chunk": "Here"}

data: {"event": "token", "chunk": " is"}

data: {"event": "token", "chunk": " the"}

data: {"event": "token", "chunk": " component"}

... more tokens ...

data: {"event": "progress", "step": "generation_complete", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "extracting_code", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "validating", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "validated", "attempt": 1, "max_attempts": 4, "message": "Component 'MyComponent' validated successfully!"}

data: {"event": "complete", "data": {"result": "...", "validated": true, "class_name": "MyComponent", "component_code": "...", "validation_attempts": 1}}

```

### Generation with Retry
```
data: {"event": "progress", "step": "generating", "attempt": 1, "max_attempts": 4}

... tokens ...

data: {"event": "progress", "step": "generation_complete", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "extracting_code", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "validating", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "validation_failed", "attempt": 1, "max_attempts": 4, "error": "SyntaxError: ...", "class_name": "BrokenComponent", "component_code": "..."}

data: {"event": "progress", "step": "retrying", "attempt": 1, "max_attempts": 4}

data: {"event": "progress", "step": "generating", "attempt": 2, "max_attempts": 4}

... retry flow continues ...
```

## API Key Resolution

The system uses a cascading approach to find API keys:

1. **User's Global Variables** (highest priority)
   - Stored in database via Settings > Model Providers
   - Retrieved using `variable_service.get_variable()`

2. **Environment Variables** (fallback)
   - Standard environment variable names (e.g., `OPENAI_API_KEY`)
   - Checked using `os.getenv()`

```python
# Resolution order in check_api_key()
api_key = await variable_service.get_variable(user_id, key_name, "", session)
if not api_key:
    api_key = os.getenv(key_name)
```

## Model Injection

When a provider and model are specified, the system dynamically injects the configuration into Agent nodes in the flow:

```python
# Before injection
{
    "data": {
        "nodes": [{
            "data": {
                "type": "Agent",
                "node": {
                    "template": {
                        "model": {"value": []}
                    }
                }
            }
        }]
    }
}

# After injection
{
    "data": {
        "nodes": [{
            "data": {
                "type": "Agent",
                "node": {
                    "template": {
                        "model": {
                            "value": [{
                                "category": "OpenAI",
                                "icon": "OpenAI",
                                "metadata": {
                                    "api_key_param": "api_key",
                                    "context_length": 128000,
                                    "model_class": "ChatOpenAI",
                                    "model_name_param": "model"
                                },
                                "name": "gpt-4",
                                "provider": "OpenAI"
                            }]
                        }
                    }
                }
            }
        }]
    }
}
```

## Configuration Check Response

The `/agentic/check-config` endpoint returns:

```json
{
    "configured": true,
    "configured_providers": ["Anthropic", "OpenAI"],
    "providers": [
        {
            "name": "Anthropic",
            "configured": true,
            "default_model": "claude-sonnet-4-5-20250514",
            "models": [
                {"name": "claude-sonnet-4-5-20250514", "display_name": "Claude Sonnet 4.5"},
                {"name": "claude-opus-4-20250514", "display_name": "Claude Opus 4"}
            ]
        },
        {
            "name": "OpenAI",
            "configured": true,
            "default_model": "gpt-5.2",
            "models": [
                {"name": "gpt-5.2", "display_name": "GPT-5.2"},
                {"name": "gpt-4o", "display_name": "GPT-4o"}
            ]
        }
    ],
    "default_provider": "Anthropic",
    "default_model": "claude-sonnet-4-5-20250514"
}
```

## Error Handling

### HTTP Errors

| Status | Scenario |
|--------|----------|
| 400 | No provider configured |
| 400 | Requested provider not configured |
| 400 | Unknown provider |
| 400 | Missing API key |
| 404 | Flow file not found |
| 500 | Flow execution error |

### Validation Errors

Validation errors are **not** HTTP errors. They trigger the retry loop and are reported via:
- SSE `progress` events with `step: "validation_failed"`
- Final `complete` event with `validated: false`

## Session Isolation

Each request can specify a `session_id` to isolate conversation memory:

- If provided: Uses the specified session ID
- If not provided: Generates a new UUID per request

This ensures that memory components in the flow don't leak state between different assistant conversations.

## Testing

Tests are located in `src/backend/tests/unit/agentic/`:

```
tests/unit/agentic/
├── api/
│   ├── test_code_extraction.py    # Code extraction + validation
│   ├── test_schemas.py            # Pydantic model tests
│   └── test_streaming_validation.py  # Full flow tests
├── helpers/
│   ├── test_error_handling.py     # Error message conversion
│   └── test_sse.py                # SSE formatting
└── services/
    ├── test_flow_executor.py      # Flow execution
    └── test_provider_service.py   # Provider configuration
```

Run tests with:
```bash
pytest src/backend/tests/unit/agentic/ -v
```

## Dependencies

The module depends on:

- `lfx`: Langflow execution library
  - `lfx.run.base.run_flow`: Execute flows
  - `lfx.custom.validate`: Code validation utilities
  - `lfx.base.models.unified_models`: Model provider configuration

- `langflow.services.variable`: Global variable storage
- `langflow.services.deps`: Service locator

External package:
- `markitdown>=0.1.4`: Markdown processing (added to pyproject.toml)
