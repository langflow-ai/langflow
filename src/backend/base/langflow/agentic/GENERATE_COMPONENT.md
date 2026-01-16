# Langflow Assistant

**Feature Status:** In Development
**Last Updated:** January 2025

## Overview

Langflow Assistant is an AI-powered feature that helps users with Langflow-related questions, guidance, and component creation. It supports multiple AI providers (Anthropic, OpenAI, Google Generative AI, Groq, Ollama) and allows dynamic model selection. The assistant can generate Python component code, validate it, and allow users to add components directly to their flow canvas.

## Architecture

### Backend

The backend is implemented as a FastAPI router located at:
```
src/backend/base/langflow/agentic/api/router.py
```

**API Endpoints:**
- `GET /api/v1/agentic/check-config` - Returns available providers, models, and configuration status
- `POST /api/v1/agentic/assist` - Executes the assistant flow (non-streaming)
- `POST /api/v1/agentic/assist/stream` - Executes with SSE streaming progress updates

**Key Constants:**
```python
# Validation
MAX_VALIDATION_RETRIES = 3
VALIDATION_UI_DELAY_SECONDS = 0.3  # Delay before complete event for UI feedback

# Flow configuration
LANGFLOW_ASSISTANT_FLOW = "LangflowAssistant.json"

# Preferred providers in order of priority
PREFERRED_PROVIDERS = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"]

# Default models per provider
DEFAULT_MODELS = {
    "Anthropic": "claude-sonnet-4-5-20250514",
    "OpenAI": "gpt-5.2",
    "Google Generative AI": "gemini-2.0-flash",
    "Groq": "llama-3.3-70b-versatile",
}

# Provider to LangChain model class mapping
MODEL_CLASS_MAP = {
    "OpenAI": "ChatOpenAI",
    "Anthropic": "ChatAnthropic",
    "Google Generative AI": "ChatGoogleGenerativeAI",
    "Groq": "ChatGroq",
    "Ollama": "ChatOllama",
}

# Code extraction patterns (regex)
PYTHON_CODE_BLOCK_PATTERN = r"```python\s*([\s\S]*?)```"      # Closed blocks
GENERIC_CODE_BLOCK_PATTERN = r"```\s*([\s\S]*?)```"          # Generic closed
UNCLOSED_PYTHON_BLOCK_PATTERN = r"```python\s*([\s\S]*)$"    # Unclosed python
UNCLOSED_GENERIC_BLOCK_PATTERN = r"```\s*([\s\S]*)$"         # Unclosed generic

# Error categorization for friendly messages
ERROR_PATTERNS = [
    (["rate_limit", "429"], "Rate limit exceeded..."),
    (["authentication", "api_key", "unauthorized", "401"], "Authentication failed..."),
    (["quota", "billing", "insufficient"], "API quota exceeded..."),
    ...
]
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `inject_model_into_flow()` | Injects selected provider/model into the flow's Agent component |
| `execute_flow_file()` | Executes a flow JSON file with user context and model injection |
| `execute_flow_with_validation()` | Non-streaming validation loop |
| `execute_flow_with_validation_streaming()` | Async generator yielding SSE progress events |
| `validate_component_code()` | Validates Python code using `create_class()` from lfx |
| `extract_python_code()` | Extracts code from markdown (handles closed and unclosed blocks) |
| `_find_code_blocks()` | Finds all code blocks in text |
| `_find_unclosed_code_block()` | Handles LLM responses that don't close ```python blocks |
| `_find_component_code()` | Finds the code block containing a Component class |
| `get_enabled_providers_for_user()` | Gets enabled providers based on user's configured API keys |
| `check_api_key()` | Checks for API key in global variables or environment |
| `_extract_friendly_error()` | Converts technical errors to user-friendly messages |
| `_sse_progress()` | Formats SSE progress event |
| `_sse_complete()` | Formats SSE complete event |
| `_sse_error()` | Formats SSE error event |

**Flow Execution:**
The feature uses a pre-built flow located at:
```
src/backend/base/langflow/agentic/flows/LangflowAssistant.json
```

### SSE Streaming Protocol

The `/assist/stream` endpoint uses Server-Sent Events (SSE) for real-time progress updates.

**Step Types:**

| Step | Description | Icon |
|------|-------------|------|
| `generating` | LLM is generating response | Sparkles (blue) |
| `generation_complete` | LLM finished generating | Check (green) |
| `extracting_code` | Extracting Python code from response | FileCode (purple) |
| `validating` | Validating component code | Shield (yellow, spinning) |
| `validated` | Validation succeeded | CheckCircle (green) |
| `validation_failed` | Validation failed | XCircle (red) |
| `retrying` | About to retry with error context | RefreshCw (orange, spinning) |

**Event Types:**

```json
// Progress events - sent during each step
{"event": "progress", "step": "generating", "attempt": 1, "max_attempts": 4, "message": "Generating component code (attempt 1/4)..."}
{"event": "progress", "step": "generation_complete", "attempt": 1, "max_attempts": 4, "message": "Code generation complete"}
{"event": "progress", "step": "extracting_code", "attempt": 1, "max_attempts": 4, "message": "Extracting Python code from response..."}
{"event": "progress", "step": "validating", "attempt": 1, "max_attempts": 4, "message": "Validating component code..."}

// On success:
{"event": "progress", "step": "validated", "attempt": 1, "max_attempts": 4, "message": "Component 'MyComponent' validated successfully!"}

// On failure:
{"event": "progress", "step": "validation_failed", "attempt": 1, "max_attempts": 4, "message": "Validation failed", "error": "SyntaxError: ..."}
{"event": "progress", "step": "retrying", "attempt": 1, "max_attempts": 4, "message": "Retrying with error context (attempt 2/4)...", "error": "SyntaxError: ..."}

// Complete event - sent when done (success or failure)
{
  "event": "complete",
  "data": {
    "result": "...",           // Full LLM response
    "validated": true,         // Validation success
    "class_name": "MyComponent", // Component class name
    "component_code": "...",   // Extracted Python code
    "validation_attempts": 1   // Number of attempts made
  }
}

// Error event - sent on flow execution failure
{"event": "error", "message": "Rate limit exceeded. Please wait a moment and try again."}
```

**SSE Response Format:**
```
data: {"event": "progress", ...}\n\n
data: {"event": "complete", ...}\n\n
```

### Validation Loop

```
User Prompt
    ↓
┌───────────────────────────────────────────────┐
│ For attempt 1 to max_retries + 1:              │
│   ↓                                            │
│   [SSE: progress/generating]                   │
│   ↓                                            │
│   Execute LLM flow                             │
│   ↓                                            │
│   [SSE: progress/generation_complete]          │
│   ↓                                            │
│   [SSE: progress/extracting_code]              │
│   ↓                                            │
│   Extract Python code from response            │
│   ↓                                            │
│   No code? → [SSE: complete] return            │
│   ↓                                            │
│   [SSE: progress/validating]                   │
│   ↓                                            │
│   Validate with create_class()                 │
│   ↓                                            │
│   Valid? → [SSE: progress/validated]           │
│          → [SSE: complete] return              │
│   ↓                                            │
│   [SSE: progress/validation_failed]            │
│   ↓                                            │
│   Max attempts? → [SSE: complete with error]   │
│   ↓                                            │
│   [SSE: progress/retrying]                     │
│   ↓                                            │
│   Prepare retry with error context             │
└───────────────────────────────────────────────┘
```

### Code Extraction

The `extract_python_code()` function handles multiple scenarios:

1. **Closed Python blocks**: ` ```python ... ``` `
2. **Closed generic blocks**: ` ``` ... ``` `
3. **Unclosed Python blocks**: ` ```python ... ` (no closing backticks)
4. **Unclosed generic blocks**: ` ``` ... ` (no closing backticks)
5. **Text before code**: Apology text + code block
6. **Multiple blocks**: Prefers block containing `class` and `Component`

### Frontend

**Component Location:**
```
src/frontend/src/components/core/generateComponent/
├── index.tsx                       # Main component (GenerateComponent)
├── generate-component-terminal.tsx # Terminal UI component
└── types.ts                        # TypeScript type definitions
```

**API Hooks:**
```
src/frontend/src/controllers/API/queries/generate-component/
├── index.ts
├── use-get-generate-component-config.ts  # GET /agentic/check-config
└── use-post-generate-component-prompt.ts # POST /agentic/assist/stream
```

**SSE Client Implementation (`use-post-generate-component-prompt.ts`):**

```typescript
// Key types
type SSEEvent = {
  event: "progress" | "complete" | "error";
  step?: "generating" | "validating";
  attempt?: number;
  max_attempts?: number;
  data?: GenerateComponentPromptResponse;
  message?: string;
};

// Key functions
postGenerateComponentPromptStream()  // Main streaming function
fetchStreamingResponse()             // Fetch with SSE headers
processSSEStream()                   // Process ReadableStream
splitSSEEvents()                     // Split buffer on \n\n
processSSEEvent()                    // Parse individual events
parseSSEEvent()                      // JSON.parse with error handling
```

**Types (`types.ts`):**

```typescript
export type ProgressState = {
  step: "generating" | "validating";
  attempt: number;
  maxAttempts: number;
};

export type SubmitResult = {
  content: string;
  validated?: boolean;
  className?: string;
  validationError?: string;
  validationAttempts?: number;
  componentCode?: string;
};

export type GenerateComponentPromptResponse = {
  result?: string;
  text?: string;
  validated?: boolean;
  class_name?: string;
  validation_error?: string;
  validation_attempts?: number;
  component_code?: string;
};
```

**URL Constants (`constants.ts`):**
```typescript
GENERATE_COMPONENT_PROMPT: "agentic/assist"
GENERATE_COMPONENT_PROMPT_STREAM: "agentic/assist/stream"
GENERATE_COMPONENT_CHECK_CONFIG: "agentic/check-config"
```

### User Interface

**Terminal Features:**
- Resizable terminal panel (200px - 600px height)
- Command history with arrow key navigation (stored in sessionStorage)
- Multi-line input with auto-resize textarea
- **Real-time progress indicator:**
  - "Generating..." during LLM generation
  - "Validating... attempt X/Y" during code validation
- Checkmark icon next to validated component names
- Configurable max retries (0-5) via terminal commands
- Dynamic model selector in the header
- Semantic color system using project palette

**Terminal Commands:**
- `MAX_RETRIES=<0-5>` - Set validation retry attempts
- `HELP` or `?` - Show help message
- `CLEAR` - Clear terminal history

**Component Result Actions:**
1. **View Code** (expand chevron) - Expands inline code viewer
2. **Download** (download icon) - Downloads as `.py` file
3. **Save to Sidebar** (save icon) - Saves to "Saved" section
4. **Add to Canvas** (`+` button) - Adds to current flow

## Data Flow

```
User Input (Terminal)
       ↓
POST /agentic/assist/stream
       ↓
inject_model_into_flow() - Configure Agent
       ↓
execute_flow_with_validation_streaming()
       ↓
┌──────────────────────────────────────────┐
│ SSE Events:                              │
│ ← progress: {generating, 1/4}            │
│ ← progress: {validating, 1/4}            │
│ [if retry needed]                        │
│ ← progress: {generating, 2/4}            │
│ ← progress: {validating, 2/4}            │
│ ...                                      │
│ ← complete: {validated, code, class}     │
└──────────────────────────────────────────┘
       ↓
Frontend displays result with action buttons
       ↓
[User clicks action button]
       ↓
POST /custom_component/validate
       ↓
useAddComponent() or useAddFlow()
```

## Error Handling

**Friendly Error Messages:**
The `_extract_friendly_error()` function converts technical errors:

| Pattern | Friendly Message |
|---------|------------------|
| `rate_limit`, `429` | "Rate limit exceeded. Please wait a moment and try again." |
| `authentication`, `api_key`, `401` | "Authentication failed. Check your API key." |
| `quota`, `billing` | "API quota exceeded. Please check your account billing." |
| `timeout` | "Request timed out. Please try again." |
| `connection`, `network` | "Connection error. Please check your network." |
| `500`, `internal server error` | "Server error. Please try again later." |

**Error Event Flow:**
1. Flow execution catches HTTPException or specific exceptions
2. Error message extracted and converted to friendly format
3. SSE error event sent to frontend
4. Frontend displays error message in terminal

## Testing

**Test Files:**
```
src/backend/tests/unit/agentic/api/
├── __init__.py
├── test_code_extraction.py      # 31 tests
└── test_streaming_validation.py # 22 tests
```

**Test Coverage:**
- `extract_python_code()` - closed/unclosed blocks, text before code
- `validate_component_code()` - valid/invalid/incomplete code
- `_find_code_blocks()` - all block types
- `_find_unclosed_code_block()` - unclosed pattern matching
- SSE event formatting
- Streaming validation flow with retries
- Error handling and retry behavior
- Real-world scenarios (text + incomplete code)

**Run Tests:**
```bash
uv run pytest src/backend/tests/unit/agentic/api/ -v
```

## Configuration Requirements

The feature requires at least one model provider to be configured:

| Provider | API Key Variable |
|----------|------------------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google Generative AI | `GOOGLE_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Ollama | Local installation |

API keys can be configured in:
1. Environment variables
2. Langflow Settings > Model Providers

## Technical Decisions

### SSE vs WebSockets
SSE was chosen over WebSockets because:
- Simpler implementation for unidirectional server-to-client updates
- HTTP/2 compatible, works through proxies
- Auto-reconnect built into browser EventSource API
- Sufficient for progress updates (no bidirectional communication needed)

### Code Extraction Strategy
The extraction logic handles multiple edge cases:
1. Tries closed `\`\`\`python` blocks first (most common)
2. Falls back to generic `\`\`\`` blocks
3. Finally tries unclosed blocks (LLM truncation/errors)
4. Searches entire text, not just from start (handles apology text)

### Validation Retry Template
```python
VALIDATION_RETRY_TEMPLATE = """The previous component code has an error. Please fix it.

ERROR:
{error}

BROKEN CODE:
\`\`\`python
{code}
\`\`\`

Please provide a corrected version of the component code."""
```

### UI Delay for Progress Feedback
A 0.3s delay (`VALIDATION_UI_DELAY_SECONDS`) is added before sending the complete event to ensure the "Validating..." message is visible to users, improving perceived responsiveness.

## Files Modified/Created

### Created
- `src/frontend/src/components/core/generateComponent/` (entire folder)
- `src/frontend/src/controllers/API/queries/generate-component/` (entire folder)
- `src/frontend/src/stores/generateComponentStore.ts`
- `src/backend/tests/unit/agentic/api/test_code_extraction.py`
- `src/backend/tests/unit/agentic/api/test_streaming_validation.py`

### Modified
- `src/frontend/src/controllers/API/helpers/constants.ts` - Added URL constants
- `src/frontend/src/components/ui/select.tsx` - Added hover effect
- `src/backend/base/langflow/agentic/api/router.py` - SSE streaming, code extraction improvements

## Naming Convention

**Current naming:**
- Component: `GenerateComponent` / `GenerateComponentTerminal`
- Store: `generateComponentStore`
- API route: `/agentic/assist`, `/agentic/assist/stream`
- UI label: "Assistant"
