# Langflow Assistant Panel

**Feature Status:** In Active Development
**Last Updated:** January 2025
**Branch:** `cz/agentic-api`

## Overview

The Langflow Assistant Panel is a chat-based AI assistant that helps users generate custom Langflow components. It features:

- **SSE Streaming**: Real-time progress updates during component generation
- **Intent Detection**: Automatically detects component generation vs Q&A requests
- **Validation with Retry**: Auto-validates generated code and retries with error context
- **Animated Reasoning UI**: Terminal-style loading state with typing animation
- **Randomized Messages**: 8 variations for each UI message to feel more natural
- **Multi-Provider Support**: Works with Anthropic, OpenAI, Google, Groq, Ollama

## Architecture

### Backend Structure

```
src/backend/base/langflow/agentic/
├── api/
│   ├── router.py          # FastAPI endpoints (/assist, /assist/stream, /check-config)
│   └── schemas.py         # Pydantic schemas and types
├── helpers/
│   ├── code_extraction.py # Extract Python code from LLM responses
│   ├── error_handling.py  # Convert technical errors to friendly messages
│   ├── sse.py             # SSE event formatting (progress, token, complete, error)
│   └── validation.py      # Validate component code using create_class()
├── services/
│   ├── assistant_service.py  # Main service with validation loop
│   ├── flow_executor.py      # Execute flow files with streaming
│   ├── flow_preparation.py   # Prepare flow with model injection
│   └── provider_service.py   # Provider/model configuration
└── flows/
    └── LangflowAssistant.json  # Pre-built assistant flow
```

### Frontend Structure

```
src/frontend/src/components/core/assistantPanel/
├── assistant-panel.tsx           # Main panel component with state management
├── assistant-panel.types.ts      # TypeScript interfaces
├── components/
│   ├── assistant-header.tsx          # Header with close/clear buttons
│   ├── assistant-input.tsx           # Message input with model selector
│   ├── assistant-message.tsx         # Message item (user/assistant)
│   ├── assistant-loading-state.tsx   # Animated reasoning UI
│   ├── assistant-component-result.tsx # Component card with Approve button
│   ├── assistant-validation-failed.tsx # Error card when validation fails
│   ├── assistant-empty-state.tsx      # Welcome state with suggestions
│   └── assistant-no-models-state.tsx  # No models configured state
└── helpers/
    └── messages.ts               # Randomized message variations
```

### API Layer

```
src/frontend/src/controllers/API/queries/agentic/
├── index.ts                    # Exports
├── types.ts                    # SSE event types
└── use-post-assist-stream.ts   # SSE client implementation
```

## API Endpoints

### POST `/api/v1/agentic/assist/stream`

Main streaming endpoint for the assistant.

**Request:**
```typescript
interface AgenticAssistRequest {
  flow_id: string;        // Current flow ID
  input_value: string;    // User message
  provider?: string;      // e.g., "Anthropic"
  model_name?: string;    // e.g., "claude-sonnet-4-5-20250514"
  max_retries?: number;   // Default: 3
  session_id?: string;    // For conversation continuity
}
```

**Response:** Server-Sent Events stream

### GET `/api/v1/agentic/check-config`

Returns available providers and models.

**Response:**
```typescript
{
  configured: boolean;
  configured_providers: string[];
  providers: Array<{
    name: string;
    configured: boolean;
    default_model: string;
    models: Array<{ name: string; display_name: string }>;
  }>;
  default_provider: string;
  default_model: string;
}
```

## SSE Protocol

### Event Types

The streaming endpoint emits 4 types of events:

#### 1. Progress Event
```json
{
  "event": "progress",
  "step": "generating_component" | "extracting_code" | "validating" | "validated" | "validation_failed" | "retrying",
  "attempt": 0,
  "max_attempts": 3,
  "message": "Generating response..."
}
```

#### 2. Token Event (Q&A only)
```json
{
  "event": "token",
  "chunk": "partial response text"
}
```

#### 3. Complete Event
```json
{
  "event": "complete",
  "data": {
    "result": "Full LLM response text",
    "validated": true,
    "class_name": "MyComponent",
    "component_code": "class MyComponent(Component):...",
    "validation_attempts": 1
  }
}
```

#### 4. Error Event
```json
{
  "event": "error",
  "message": "Rate limit exceeded. Please wait a moment and try again."
}
```

### Step Types

| Step | Description |
|------|-------------|
| `generating` | Q&A mode: LLM is generating (tokens streamed) |
| `generating_component` | Component mode: LLM is generating (no token streaming, shows reasoning UI) |
| `generation_complete` | LLM finished generating |
| `extracting_code` | Extracting Python code from response |
| `validating` | Running code validation |
| `validated` | Code validated successfully |
| `validation_failed` | Validation failed, may retry |
| `retrying` | Retrying with error context |

### Intent Detection

The backend automatically detects if the user wants to generate a component based on patterns:

```python
COMPONENT_GENERATION_PATTERNS = [
    r"\b(generate|create|make|build|write)\b.{0,30}\b(component|custom component)\b",
    r"\b(component|custom component)\b.{0,30}\b(that|which|to|for|with)\b",
    r"\bcreate\s+(a|an|the)\s+\w+\s+component\b",
    # ... more patterns
]
```

**Component Generation Mode:**
- Shows animated reasoning UI (no token streaming)
- Validates extracted code
- Retries on validation failure

**Q&A Mode:**
- Streams tokens in real-time
- No validation step
- Returns plain text response

## Validation Flow

```
User Message
    │
    ▼
┌─────────────────────────────────────┐
│ Intent Detection                     │
│ (is this a component request?)       │
└─────────────────────────────────────┘
    │
    ▼ Component Request
┌─────────────────────────────────────┐
│ For attempt 0 to MAX_RETRIES:        │
│   │                                  │
│   ▼                                  │
│   [progress: generating_component]   │
│   │                                  │
│   ▼                                  │
│   Execute LLM Flow                   │
│   │                                  │
│   ▼                                  │
│   [progress: extracting_code]        │
│   Extract Python code from response  │
│   │                                  │
│   ├── No code found ──► [complete]   │
│   │                      (Q&A result)│
│   ▼                                  │
│   [progress: validating]             │
│   Validate with create_class()       │
│   │                                  │
│   ├── Valid ──► [progress: validated]│
│   │             [complete] ◄─────────┤
│   │                                  │
│   ▼ Invalid                          │
│   [progress: validation_failed]      │
│   │                                  │
│   ├── Max attempts ──► [complete]    │
│   │                    (with error)  │
│   ▼                                  │
│   [progress: retrying]               │
│   Prepare retry with error context   │
│   └──────────────────────────────────┘
```

### Retry Template

When validation fails, the next attempt includes error context:

```python
VALIDATION_RETRY_TEMPLATE = """The previous component code has an error. Please fix it.

ERROR:
{error}

BROKEN CODE:
```python
{code}
```

Please provide a corrected version of the component code."""
```

## Frontend State Management

### Message States

```typescript
type AssistantMessageStatus =
  | "pending"     // Initial state
  | "streaming"   // Receiving SSE events
  | "complete"    // Done (success or failure)
  | "error";      // Connection/request error
```

### Message Structure

```typescript
interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  status?: AssistantMessageStatus;
  progress?: AgenticProgressState;    // Current step info
  completedSteps?: AgenticStepType[]; // History of steps
  result?: AgenticResult;             // Final result with component
  error?: string;                     // Error message
}
```

### UI State Flow

```
┌────────────────────────────────────────────────────────────┐
│                    Message States                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  User sends message                                        │
│       │                                                    │
│       ▼                                                    │
│  [streaming] + No content                                  │
│       │        └─► ThinkingIndicator ("Thinking...")       │
│       │                                                    │
│       ▼                                                    │
│  [streaming] + progress.step = "generating_component"      │
│       │        └─► AssistantLoadingState (reasoning UI)    │
│       │                                                    │
│       ▼                                                    │
│  [streaming] + progress.step = "validating"                │
│       │        └─► AssistantLoadingState continues         │
│       │                                                    │
│       ▼                                                    │
│  [complete] + result.validated = true                      │
│       │        └─► AssistantComponentResult (approve card) │
│       │                                                    │
│       ├── OR ──────────────────────────────────────────────┤
│       │                                                    │
│       ▼                                                    │
│  [complete] + result.validated = false                     │
│       │        └─► AssistantValidationFailed (error card)  │
│       │                                                    │
│       ├── OR ──────────────────────────────────────────────┤
│       │                                                    │
│       ▼                                                    │
│  [error]                                                   │
│            └─► Error message in red                        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Animated Reasoning UI

The `AssistantLoadingState` component shows a terminal-style animation during component generation:

### Features
- **Typing Animation**: Messages appear character by character (30ms/char)
- **Message Queue**: Validation messages queued and typed in order
- **Blinking Cursor**: Appears at end of last line when waiting
- **Step Persistence**: Uses `Set<string>` to track shown steps (prevents duplicates)

### Animation Flow

```
1. Type: "Analyzing component requirements..."
2. Type: "Identifying input parameters..."
3. Type: "Checking installed libraries..."
4. Type: "Generating component code..."
   [Wait for validation step from backend]
5. Type: "Validating component..."
   [If validation fails]
6. Type: "Validation failed, analyzing errors..."
7. Type: "Retrying with fixes..."
   [Loop back to validating]
```

### Key Implementation Details

```typescript
// Track which validation steps we've shown (prevents duplicates)
const queuedValidationStepsRef = useRef<Set<string>>(new Set());

// Queue of validation messages to type
const validationQueueRef = useRef<string[]>([]);

// Messages are generated once per component instance (useMemo)
const reasoningMessages = useMemo(() => getRandomReasoningMessages(), []);
```

## Randomized Messages

Each UI message has 8 variations. Messages are selected randomly per component instance using `useMemo`.

### Message Categories

| Category | Example Variations |
|----------|-------------------|
| Reasoning Header | "Reasoning...", "Thinking...", "Processing...", "Working on it...", "Analyzing...", "Building...", "Generating...", "Creating..." |
| Analyzing | "Analyzing component requirements...", "Understanding your component needs...", "Reviewing the component specifications..." |
| Identifying Inputs | "Identifying input parameters...", "Determining required inputs...", "Mapping out input fields..." |
| Checking Dependencies | "Checking installed libraries & dependencies...", "Verifying available dependencies...", "Reviewing library requirements..." |
| Generating Code | "Generating component code...", "Writing the component logic...", "Building the component code..." |
| Validating | "Validating component...", "Checking component validity...", "Verifying the component..." |
| Validation Failed | "Validation failed, analyzing errors...", "Found issues, reviewing errors...", "Detected errors, analyzing..." |
| Retrying | "Retrying with fixes...", "Applying corrections and retrying...", "Making adjustments and trying again..." |
| Component Created | "I've created the component you asked for.", "Your component is ready to use.", "Here's the component you requested." |

### Usage

```typescript
// In component (randomized once per instance)
const componentCreatedMessage = useMemo(() => getRandomComponentCreatedMessage(), []);
const thinkingMessage = useMemo(() => getRandomThinkingMessage(), []);
```

## Component Result Card

When a component is successfully generated:

### UI Elements
- **Icon**: FileText icon with `#0EA5E9` blue background
- **Component Name**: Extracted class name (e.g., "MyComponent")
- **Features Section**: Static list of features with `pl-4` padding
- **Approve Button**: White button, shows "Approved" for 3 seconds then reverts

### Approve Flow

```typescript
const handleApprove = () => {
  onApprove();                    // Calls parent handler
  setShowApproved(true);          // Shows "Approved" state
};

useEffect(() => {
  if (showApproved) {
    const timer = setTimeout(() => {
      setShowApproved(false);     // Reverts after 3 seconds
    }, APPROVED_DISPLAY_DURATION_MS);
    return () => clearTimeout(timer);
  }
}, [showApproved]);
```

### Adding to Canvas

When approved, the component is validated again and added to the canvas:

```typescript
const handleApprove = async (messageId: string) => {
  const message = messages.find((m) => m.id === messageId);
  if (!message?.result?.componentCode) return;

  const response = await validateComponent({
    code: message.result.componentCode,
    frontend_node: {} as APIClassType,
  });

  if (response.data) {
    addComponent(response.data, response.type || "CustomComponent");
  }
};
```

## Validation Failed Card

When all retries fail, shows:
- Error message
- Expandable code view
- Visual error indicator

## Configuration Requirements

### Required: At least one model provider

| Provider | API Key Variable |
|----------|------------------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google Generative AI | `GOOGLE_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Ollama | Local installation (no key needed) |

### Default Models

```python
DEFAULT_MODELS = {
    "Anthropic": "claude-sonnet-4-5-20250514",
    "OpenAI": "gpt-5.2",
    "Google Generative AI": "gemini-2.0-flash",
    "Groq": "llama-3.3-70b-versatile",
}
```

### Provider Priority

When no provider is specified, uses first available from:
1. Anthropic
2. OpenAI
3. Google Generative AI
4. Groq

## Key Constants

### Backend

```python
# assistant_service.py
MAX_VALIDATION_RETRIES = 3
VALIDATION_UI_DELAY_SECONDS = 0.3  # Delay for UI feedback
LANGFLOW_ASSISTANT_FLOW = "LangflowAssistant.json"
```

### Frontend

```typescript
// assistant-loading-state.tsx
const TYPING_SPEED = 30;        // ms per character
const MESSAGE_DELAY = 400;      // ms between messages

// assistant-component-result.tsx
const APPROVED_DISPLAY_DURATION_MS = 3000;  // 3 seconds
```

## Error Handling

### Friendly Error Messages

Technical errors are converted to user-friendly messages:

| Pattern | Friendly Message |
|---------|------------------|
| `rate_limit`, `429` | "Rate limit exceeded. Please wait a moment and try again." |
| `authentication`, `api_key`, `401` | "Authentication failed. Check your API key." |
| `quota`, `billing` | "API quota exceeded. Please check your account billing." |
| `timeout` | "Request timed out. Please try again." |
| `connection`, `network` | "Connection error. Please check your network." |
| `500`, `internal server error` | "Server error. Please try again later." |

## Testing

### Backend Tests

```bash
uv run pytest src/backend/tests/unit/agentic/api/ -v
```

Test files:
- `test_code_extraction.py` - Code extraction from LLM responses
- `test_streaming_validation.py` - SSE streaming and validation flow

### Manual Testing

1. **Component Generation**: "Create a component that fetches data from an API"
2. **Q&A Mode**: "What is a component in Langflow?"
3. **Validation Retry**: Request a complex component that may fail validation
4. **Error States**: Disconnect network or use invalid API key

## Development Guidelines

### Adding New Message Variations

Edit `helpers/messages.ts`:

```typescript
const NEW_MESSAGES = [
  "Variation 1...",
  "Variation 2...",
  // Add 8 total variations
];

export function getRandomNewMessage(): string {
  return getRandomMessage(NEW_MESSAGES);
}
```

### Adding New Progress Steps

1. **Backend** (`schemas.py`): Add to `StepType`
2. **Backend** (`assistant_service.py`): Yield new progress event
3. **Frontend** (`types.ts`): Add to `AgenticStepType`
4. **Frontend** (`assistant-message.tsx`): Add to `componentGenerationSteps`
5. **Frontend** (`assistant-loading-state.tsx`): Handle new step in animation

### Modifying Retry Behavior

Edit `assistant_service.py`:

```python
MAX_VALIDATION_RETRIES = 3  # Change retry count

VALIDATION_RETRY_TEMPLATE = """..."""  # Modify retry prompt
```

## Files Reference

### Core Files

| File | Purpose |
|------|---------|
| `assistant-panel.tsx` | Main panel with message state management |
| `assistant-message.tsx` | Renders individual messages with appropriate UI |
| `assistant-loading-state.tsx` | Animated reasoning terminal |
| `assistant-component-result.tsx` | Component card with approve button |
| `assistant-validation-failed.tsx` | Error card when validation fails |
| `helpers/messages.ts` | Randomized message variations |
| `use-post-assist-stream.ts` | SSE client for streaming |
| `assistant_service.py` | Backend validation loop with streaming |
| `sse.py` | SSE event formatting |

### Type Definitions

| File | Purpose |
|------|---------|
| `assistant-panel.types.ts` | Frontend message/model types |
| `agentic/types.ts` | SSE event types |
| `schemas.py` | Backend Pydantic schemas |

## Changelog

### January 2025

- Initial Assistant Panel implementation
- SSE streaming with progress events
- Validation retry logic (up to 3 retries)
- Animated reasoning UI with typing effect
- Queue-based message persistence (fixes looping bug)
- Randomized messages (8 variations each)
- Component result card with 3-second approve feedback
- Validation failed card with error display
- Intent detection for component vs Q&A mode
- Token streaming for Q&A responses

## Future Improvements

- [ ] View Code button for generated components
- [ ] Copy code functionality
- [ ] Download component as .py file
- [ ] Conversation history persistence
- [ ] Multi-turn conversation support
- [ ] Component preview before adding to canvas
