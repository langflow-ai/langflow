# Feature: Langflow Assistant

> Generated on: 2026-01-21
> Updated on: 2026-03-30
> Updated on: 2026-05-19
> Status: Draft
> Owner: Engineering Team

> **2026-05-19 revision** — Single-agent-loop pivot (Claude Code / Codex pattern):
> the assistant is now ONE agent + an MCP toolkit instead of a multi-phase
> orchestrator. New MCP tools `GenerateComponent`, `DescribeFlowIO`, and
> `RunFlow`; run metrics surfaced on completion; edit+run continuation gating;
> provider-agnostic in-flow model selection (no OpenAI obligation); an
> "Orchestrating..." progress step for multi-step prompts. Single-thing
> requests are byte-identical to the previous experience.

> **Companion docs**: end-to-end architecture (with Mermaid sequence/flow
> diagrams) lives at
> `src/backend/base/langflow/agentic/ARCHITECTURE.md`. This document covers the
> product/feature-level model; refer to ARCHITECTURE.md for the internal
> single-agent-loop and MCP tool wiring.

---

## Table of Contents
1. [Overview](#1-overview)
2. [Ubiquitous Language Glossary](#2-ubiquitous-language-glossary)
3. [Domain Model](#3-domain-model)
4. [Behavior Specifications](#4-behavior-specifications)
5. [Architecture Decision Records](#5-architecture-decision-records)
6. [Technical Specification](#6-technical-specification)
7. [Observability](#7-observability)
8. [Deployment & Rollback](#8-deployment--rollback)
9. [Architecture Diagrams](#9-architecture-diagrams)

---

## 1. Overview

### Summary

The Langflow Assistant is an AI-powered chat interface that helps users generate custom Langflow components through natural language prompts. It provides real-time streaming feedback during component generation, automatic code validation with retry logic, and seamless integration with the Langflow canvas.

### Business Context

Building custom components in Langflow requires knowledge of the component architecture, Python programming, and understanding of inputs/outputs. The Langflow Assistant removes this barrier by allowing users to describe what they want in natural language, and the AI generates validated, ready-to-use component code that can be added directly to their flow.

### Bounded Context

**Context**: `Agentic` - AI-assisted development capabilities within Langflow

This context owns:
- AI assistant interactions and chat management
- Component code generation and validation
- Streaming progress updates and token delivery
- Model provider integration and configuration

### Related Contexts

| Context | Relationship | Description |
|---------|--------------|-------------|
| `Flow` | Customer-Supplier | Assistant generates components that integrate with flows; Flow context supplies flow IDs and component APIs |
| `Model Providers` | Conformist | Assistant conforms to configured model providers (OpenAI, Anthropic, etc.) for LLM capabilities |
| `Variables` | Customer-Supplier | Variables context supplies API keys; Assistant uses them for model authentication |
| `Custom Components` | Customer-Supplier | Custom Components context supplies validation APIs; Assistant uses them to validate generated code |

---

## 2. Ubiquitous Language Glossary

| Term | Definition | Code Reference |
|------|------------|----------------|
| **Assistant** | AI-powered chat interface that generates Langflow components from natural language | `AssistantPanel`, `AssistantService` |
| **AssistantMessage** | A single message in the chat, either from user or assistant | `AssistantMessage` interface |
| **ComponentCode** | Python code that defines a Langflow component with inputs, outputs, and processing logic | `component_code` field, `extract_component_code()` |
| **IntentClassification** | LLM-based detection of whether user wants to generate a component, ask a question, or is off-topic | `classify_intent()`, `IntentResult` |
| **ProgressStep** | A discrete stage in the component generation pipeline (generating, validating, etc.) | `StepType`, `AgenticStepType` |
| **SSE** | Server-Sent Events - Protocol for streaming real-time progress updates from server to client | `StreamingResponse`, `postAssistStream()` |
| **TokenEvent** | Real-time streaming of LLM output tokens for Q&A responses | `AgenticTokenEvent`, `format_token_event()` |
| **Validation** | Two-phase process: static AST analysis (`validate_component_code()`) followed by runtime instantiation (`validate_component_runtime()`) | `validate_component_code()`, `validate_component_runtime()`, `ValidationResult` |
| **ValidationRetry** | Automatic re-generation attempt when validation fails, including error context | `VALIDATION_RETRY_TEMPLATE`, `max_retries` |
| **FloatingPanel** | The assistant panel displayed as a floating overlay centered on the canvas | `AssistantPanel` |
| **ModelProvider** | External LLM service (OpenAI, Anthropic, etc.) used for generation | `provider`, `PREFERRED_PROVIDERS` |
| **EnabledProvider** | A model provider that has been configured with valid API credentials | `get_enabled_providers_for_user()` |
| **FlowExecutor** | Service that runs Langflow flows programmatically for assistant operations | `FlowExecutor`, `execute_flow_file()` |
| **TranslationFlow** | Pre-built flow that translates user input and classifies intent | `TranslationFlow.json`, `TRANSLATION_FLOW` |
| **LangflowAssistantFlow** | Pre-built flow containing the main assistant prompt and component generation logic | `LangflowAssistant.json`, `LANGFLOW_ASSISTANT_FLOW` |
| **ReasoningUI** | Animated typing display showing "thinking" messages during component generation | `AssistantLoadingState` |
| **ApproveAction** | User action to add a validated component to the canvas | `handleApprove()`, `addComponent()` |
| **OffTopic** | Intent classification for questions unrelated to Langflow (other tools, general knowledge) | `"off_topic"`, `OFF_TOPIC_REFUSAL_MESSAGE` |
| **RuntimeValidation** | Second-phase validation that instantiates the component class to catch import/runtime errors | `validate_component_runtime()`, `build_custom_component_template()` |
| **AgenticSessionPrefix** | `agentic_` prefix on session IDs to isolate Assistant sessions from Playground | `AGENTIC_SESSION_PREFIX` |
| **SingleAgentLoop** | The assistant is one agent (`flow_builder_assistant.py`) plus an MCP toolkit; the same loop chains tools for multi-thing prompts instead of spawning sub-agents (Claude Code / Codex pattern) | `flow_builder_assistant.py`, `src/lfx/src/lfx/mcp/flow_builder_tools.py` |
| **GenerateComponent** | MCP tool that re-enters the full component validation pipeline mid-loop, registers the user component, and returns `class_name` so `SearchComponentTypes` can find it | `GenerateComponent` (`flow_builder_tools.py`) |
| **DescribeFlowIO** | MCP tool that deterministically classifies a flow's inputs/outputs/tool components from the actual wiring (scalable for large flows; replaces guess-by-name) | `DescribeFlowIO` (`flow_builder_tools.py`) |
| **RunFlow** | MCP tool that executes the canvas flow and returns the result plus run metrics | `RunFlow` (`flow_builder_tools.py`), `agentic/services/flow_run.py` |
| **RunMetrics** | `{duration_seconds, input_tokens, output_tokens, total_tokens}` returned by `RunFlow`; duration via `perf_counter`, tokens via `extract_graph_token_usage` over graph vertices | `agentic/services/flow_run.py`, `extract_graph_token_usage` |
| **OrchestratingStep** | Progress step/label ("Orchestrating...") chosen for compound or build+run prompts; the run detector is a post-LLM rescue, not a pre-LLM override | `agentic/services/request_framing.py::decide_progress_step` |
| **EditContinuation** | After the user approves proposed canvas edits, the frontend saves the flow then silently re-sends `EDIT_CONTINUATION_INPUT` so the SAME request finishes deferred steps; only fires when a deferred step existed (`continuation_expected`) | `EDIT_CONTINUATION_INPUT`, `continuation_expected` |
| **ComponentThenFlow** | Compound intent: make a component, build a flow with it, then run it — handled by the single agent loop in one request | `component_then_flow` (`translation_flow.py` / `intent_classification.py`) |
| **AvailableModelProviders** | Detects providers that actually have a configured key and injects an `[Available language models ...]` block into the prompt; no fixed OpenAI/Anthropic obligation for the flow's Agent node | `available_model_providers(global_variables)` (`agentic/services/flow_preparation.py`) |
| **PlanApproval** | `PLAN_APPROVAL_INPUT` is a byte-identical FE/BE protocol string matched exactly and bypassing the classifier; `propose_plan` is optional (only large/ambiguous changes stop for a plan card) | `PLAN_APPROVAL_INPUT`, `propose_plan` |

---

## 3. Domain Model

### 3.1 Aggregates

#### AssistantSession

The core aggregate managing a user's interaction session with the assistant.

- **Root Entity**: `AssistantSession` (implicit, managed via `session_id`)
- **Entities**:
  - `AssistantMessage` - Individual messages in the conversation
  - `AgenticProgressState` - Current step in generation pipeline
- **Value Objects**:
  - `AssistantModel` - Selected provider/model combination
  - `AgenticResult` - Final generation result with validation status
  - `ValidationResult` - Outcome of code validation
  - `IntentResult` - Translation and intent classification
- **Invariants**:
  - A session must have a valid `flow_id` to generate components
  - Only one message can be in `streaming` status at a time
  - `session_id` is generated once per session on the frontend and reused across all requests in the same session
  - A new `session_id` is only generated when the user explicitly clicks "New session"
  - `session_id` must be passed with every request to maintain conversation memory
  - The TranslationFlow must NOT share the assistant's `session_id` (it is stateless)

#### ComponentGeneration

Represents a single component generation attempt with validation.

- **Root Entity**: Generation attempt (tracked via `validation_attempts`)
- **Value Objects**:
  - `ComponentCode` - Extracted Python code
  - `ValidationResult` - Compilation and instantiation result
- **Invariants**:
  - Maximum retries cannot exceed configured `max_retries`
  - Component code must contain a class inheriting from `Component`
  - Component must define inputs or outputs to be valid

#### ModelProviderConfiguration

Configuration for available LLM providers.

- **Root Entity**: Provider configuration per user
- **Value Objects**:
  - `EnabledProvider` - Provider with valid API key
  - `ProviderModel` - Available model for a provider
- **Invariants**:
  - At least one provider must be enabled to use assistant
  - API key must be valid and non-empty for provider to be enabled
  - Provider preference order: Anthropic > OpenAI > Google Generative AI > Groq
  - IBM WatsonX and Ollama are supported with provider-specific parameter injection (URL, project ID, base URL)

#### Model Selection Behavior

The frontend implements automatic model selection to ensure a valid model is always sent to the backend:

- **Auto-selection**: When no model is explicitly selected, or when the persisted model's provider is no longer available, the first available model from enabled providers is automatically selected
- **Persistence**: Selected model is stored in localStorage (`langflow-assistant-selected-model`)
- **Validation**: On load, persisted model is validated against current enabled providers. If the provider or model no longer exists, the selection is cleared and auto-selection triggers
- **Provider icon**: The model selector trigger displays the provider's icon (e.g., Anthropic, OpenAI) instead of a generic label
- **Invariant**: A request must never be sent without a valid model selection to prevent backend fallback to unexpected providers

### 3.2 Domain Events

| Event | Trigger | Payload | Consumers |
|-------|---------|---------|-----------|
| `ProgressUpdate` | Each pipeline stage transition | `{step, attempt, max_attempts, message?, error?}` | Frontend UI (SSE) |
| `TokenGenerated` | Each LLM output token (Q&A only) | `{chunk: string}` | Frontend UI (SSE) |
| `GenerationComplete` | Pipeline finished successfully | `{result, validated, class_name?, component_code?}` | Frontend UI (SSE) |
| `GenerationError` | Unrecoverable error occurred | `{message: string}` | Frontend UI (SSE) |
| `GenerationCancelled` | User cancelled or disconnected | `{message?: string}` | Frontend UI (SSE) |
| `ValidationSucceeded` | Code compiled and instantiated | `{class_name, code}` | Assistant Service |
| `ValidationFailed` | Code failed to compile/instantiate | `{error, code, class_name?}` | Assistant Service (triggers retry) |
| `ComponentApproved` | User clicked "Add to Canvas" | `{component_code, class_name}` | Canvas (adds node) |
| `OrchestratingStarted` | Compound or build+run prompt detected (post-LLM rescue) | `{step: "orchestrating", message: "Orchestrating..."}` | Frontend UI (SSE) |
| `RunMetricsSurfaced` | `RunFlow` finished executing the canvas flow | `{duration_seconds, input_tokens, output_tokens, total_tokens}` (folded into the `complete` payload) | Frontend UI (SSE) |
| `EditContinuationResent` | User approved proposed canvas edits and a deferred step existed | `EDIT_CONTINUATION_INPUT` re-sent on the SAME request (`continuation_expected: true`) | Assistant Service |

---

## 4. Behavior Specifications

### Feature: Langflow Assistant

**As a** Langflow user
**I want** to generate custom components using natural language
**So that** I can build flows without writing Python code manually

### Background
- Given a user with an active Langflow session
- And at least one model provider is configured with a valid API key
- And the user has a flow open in the canvas

### Scenario: Generate a simple component successfully
- **Given** the assistant panel is open
- **When** I enter "Create a component that converts text to uppercase"
- **And** I click send
- **Then** I should see a "generating_component" progress indicator
- **And** I should see the reasoning UI with typing animation
- **And** I should see an "extracting_code" progress indicator
- **And** I should see a "validating" progress indicator
- **And** I should see a "validated" success indicator
- **And** I should see the generated component code
- **And** I should see an "Add to Canvas" button

### Scenario: Ask a question about Langflow
- **Given** the assistant panel is open
- **When** I enter "How do I connect two components?"
- **And** I click send
- **Then** I should see a "generating" progress indicator
- **And** I should see streaming text response
- **And** I should NOT see the validation indicators
- **And** I should NOT see an "Add to Canvas" button

### Scenario: Add generated component to canvas
- **Given** a validated component has been generated
- **When** I click the "Add to Canvas" button
- **Then** the component should be validated through the component API
- **And** the component should appear on the canvas at viewport center
- **And** I should see a success notification

### Scenario: Select a specific model for generation
- **Given** the assistant panel is open
- **And** I have multiple model providers configured
- **When** I click the model selector
- **And** I select "gpt-4o" from "openai"
- **And** I enter "Create a text splitter component"
- **And** I click send
- **Then** the generation should use the selected model
- **And** I should see the model name in the request

### Scenario: Auto-select first available model
- **Given** the assistant panel is open
- **And** I have not previously selected a model
- **And** I have at least one model provider configured
- **When** the model selector initializes
- **Then** the first available model should be automatically selected
- **And** the selected model should be persisted for future sessions

### Scenario: Maintain conversation memory across messages
- **Given** the assistant panel is open
- **And** I have previously generated a component
- **When** I ask a follow-up question like "can you use dataframe output instead?"
- **Then** the assistant should remember the previous component
- **And** it should generate a modified version of the component
- **And** I should see the same progress indicators as the initial generation
- **And** I should see the component card with "Approve" and "View Code" buttons

### Scenario: Follow-up modification classified as component generation
- **Given** I have generated a component in the current session
- **When** I send a modification request like "add error handling" or "use X instead"
- **Then** the intent should be classified as "generate_component" (not "question")
- **And** the progress card should appear immediately (no token streaming)
- **And** the validation pipeline should run as normal

### Scenario: New session resets conversation memory
- **Given** I have messages in the assistant chat
- **When** I click "New session" in the header
- **Then** all messages should be cleared
- **And** a new session ID should be generated
- **And** subsequent messages should not reference previous conversation

### Scenario: Multi-language support
- **Given** the assistant panel is open
- **When** I enter "Crie um componente que soma dois numeros" (Portuguese)
- **And** I click send
- **Then** the input should be translated to English internally
- **And** the intent should be classified as "generate_component"
- **And** I should receive a valid component that adds numbers

### Scenario: Automatic retry on validation failure
- **Given** the assistant panel is open
- **And** max_retries is set to 3 (meaning 3 total attempts)
- **When** I submit a request that generates invalid code
- **Then** I should see a "validation_failed" indicator with a clean error (not raw stacktrace)
- **And** I should see a "retrying" indicator
- **And** the system should automatically re-generate with error context
- **And** I should see "Attempt 2 of 3" in the UI (1-indexed, only shown on retries)
- **And** validation includes both static AST checks AND runtime instantiation

### Scenario: Max retries exhausted
- **Given** the assistant panel is open
- **And** max_retries is set to 3
- **When** the generated code fails validation 3 times
- **Then** I should see the "Component generation failed" card
- **And** I should see a friendly message: "The selected model was unable to generate valid component code. Try again or use a more capable model."
- **And** I should see a collapsible "Error details" section (collapsed by default)
- **And** I should see a "View code" toggle and a "Try Again" button
- **And** I should NOT see an "Add to Canvas" button

### Scenario: Ask about unrelated tools (off-topic guardrail)
- **Given** the assistant panel is open
- **When** I ask "how does n8n work?" or any question unrelated to Langflow
- **Then** the intent should be classified as "off_topic"
- **And** I should see a refusal message redirecting me to Langflow-related topics
- **And** the LLM should NOT be called for the main response (saves API cost)

### Scenario: No model provider configured
- **Given** no model providers are configured
- **When** I open the assistant panel
- **Then** I should see the "No Models Configured" empty state
- **And** the input field should be disabled
- **And** I should see a link to Settings > Model Providers

### Scenario: API key expired or invalid
- **Given** the configured API key is invalid
- **When** I submit a generation request
- **Then** I should see an error message about the API key
- **And** the error should mention configuring in Settings

### Scenario: User cancels generation
- **Given** a component generation is in progress
- **When** I click the stop button
- **Then** the generation should be cancelled
- **And** I should see a "cancelled" status on the message
- **And** the progress indicators should disappear
- **And** I should be able to send a new message

### Scenario: Open assistant with keyboard shortcut
- **Given** I am on the flow page with focus on the canvas (not in a text input)
- **When** I press the configured shortcut key (default: **A**, configurable in Settings > Shortcuts)
- **Then** the assistant panel should open
- **And** the text input should be auto-focused so I can start typing immediately
- **And** pressing the shortcut again (when not focused on the input) should close it

### Scenario: Close assistant with Escape
- **Given** the assistant panel is open
- **When** I press **Escape**
- **Then** the assistant panel should close
- **And** this should work whether focus is on the canvas or inside the assistant's text input

### Scenario: Input placeholder during generation
- **Given** a component generation or Q&A response is in progress
- **Then** the input placeholder should show "Working on it..." instead of the random suggestion text
- **And** once generation completes, the placeholder should return to normal

### Scenario: Q&A response with example code renders as text
- **Given** the user asks a question like "how do I create a component?"
- **And** the LLM response includes example component code in a markdown code block
- **When** the response completes
- **Then** the response should render as markdown text (with syntax-highlighted code block)
- **And** it should NOT trigger the component validation pipeline
- **And** it should NOT show a component card or "Add to Canvas" button

### Scenario: Component generation fallback for edge cases
- **Given** a component generation response completes
- **And** the backend did not set `result.validated` (e.g., format mismatch)
- **But** the message has `completedSteps` containing component generation steps
- **When** the content contains a Python class extending Component in a code block
- **Then** the frontend should extract and display it as a component card

### Scenario: Compound prompt — create a component, build a flow with it, and run it
- **Given** the assistant panel is open
- **When** I enter "Create a component that reverses text, build a flow that uses it, and run it"
- **Then** the intent should be classified as "component_then_flow" (compound)
- **And** I should see the "Orchestrating..." progress step
- **And** the SAME single agent loop should chain the tools: `GenerateComponent` → build the flow → `RunFlow`
- **And** no separate sub-agents should be spawned
- **And** I should see the run result followed by run metrics

### Scenario: Provider-agnostic in-flow model auto-pick (no OpenAI obligation)
- **Given** the assistant panel is open
- **And** only a non-OpenAI provider (e.g., Anthropic or Groq) has a configured API key
- **When** I ask the assistant to build a flow containing an Agent node
- **Then** the prompt should include an `[Available language models ...]` block listing only providers with a configured key
- **And** the Agent node should be wired with a provider that actually has a key (no forced OpenAI/Anthropic)
- **And** the assistant must NOT run an Agent that has no model configured

### Scenario: Orchestrating indicator on multi-step prompts
- **Given** the assistant panel is open
- **When** I enter a prompt that asks to both build a flow and run it
- **Then** `decide_progress_step` should select the `orchestrating` step
- **And** I should see an "Orchestrating..." progress label (not just "Generating...")
- **And** the run detection should occur as a post-LLM rescue, not a pre-LLM keyword override

### Scenario: Run metrics shown after a run
- **Given** the assistant has just executed a flow via `RunFlow`
- **When** the run completes
- **Then** the completion payload should include `duration_seconds`, `input_tokens`, `output_tokens`, and `total_tokens`
- **And** the duration should be measured with `perf_counter`
- **And** the token counts should be aggregated from the graph vertices via `extract_graph_token_usage`
- **And** the agent should report these metrics in its reply
- **And** there should be NO separate "run visual feedback" UI (only run + result + metrics)

### Scenario: Edit + run continuation after approval
- **Given** the assistant proposed canvas edits and the user is asked to approve them
- **And** a deferred step exists (e.g., running the flow after the edit)
- **When** I approve the proposed edits
- **Then** the frontend should save the flow first
- **And** then silently re-send `EDIT_CONTINUATION_INPUT` on the SAME request
- **And** the deferred step (running the flow) should complete in that continuation
- **And** if NO deferred step existed (`continuation_expected` is false), no continuation should fire (prevents the duplicate-message glitch)

### Scenario: propose_plan is optional
- **Given** the assistant panel is open
- **When** I ask for a small, unambiguous flow change
- **Then** the agent should apply it directly without stopping for a plan card
- **When** I ask for a large or ambiguous change
- **Then** the agent should stop and present a plan card for approval (`PLAN_APPROVAL_INPUT`)

### Scenario: Clear conversation history
- **Given** I have multiple messages in the chat
- **When** I click the "New session" button
- **Then** all messages should be removed
- **And** a new `session_id` should be generated
- **And** the panel should stay at expanded size
- **And** any in-progress generation should be cancelled

---

## 5. Architecture Decision Records

### ADR-001: Server-Sent Events (SSE) for Streaming

**Status**: Accepted

#### Context
The assistant needs to provide real-time feedback during component generation, which can take 10-60 seconds. Users need to see progress updates and token streaming to understand the system is working.

#### Decision
Use Server-Sent Events (SSE) for streaming progress updates and tokens from backend to frontend, instead of WebSockets or polling.

#### Consequences

**Benefits:**
- Simpler implementation than WebSockets (unidirectional)
- Native browser support via `fetch` with `ReadableStream`
- Automatic reconnection handling
- Works well with HTTP/2

**Trade-offs:**
- Unidirectional only (client cannot send during stream)
- Limited to text-based data (JSON encoded)
- Some proxy/firewall issues possible

**Impact on Product:**
- Users see real-time progress during generation
- Reduced perceived latency
- Better user experience during long operations

---

### ADR-002: Intent Classification via LLM

**Status**: Accepted

#### Context
The assistant needs to distinguish between component generation requests and general questions. Additionally, users may write prompts in any language.

#### Decision
Use a dedicated LLM-based TranslationFlow to classify intent and translate input to English before processing.

#### Consequences

**Benefits:**
- Accurate intent detection via LLM reasoning
- Multi-language support without explicit language detection
- Consistent English input for component generation flow

**Trade-offs:**
- Additional LLM call adds latency (~1-2 seconds)
- Additional cost per request
- Fallback needed if classification fails

**Impact on Product:**
- Users can write in any language
- Better routing between Q&A and component generation
- Slightly increased response time

---

### ADR-003: Automatic Validation with Retry

**Status**: Accepted

#### Context
LLMs sometimes generate code with syntax errors or missing imports. Manual retry is frustrating for users.

#### Decision
Automatically validate generated code by instantiating the component class. On failure, retry with error context included in the prompt.

#### Consequences

**Benefits:**
- Higher success rate for component generation
- Self-healing through error context
- Better user experience (no manual retry needed)

**Trade-offs:**
- Multiple LLM calls on failure (up to 4x cost)
- Longer total time when retries needed
- Some errors may not be fixable by retry

**Impact on Product:**
- Users get working components more often
- Reduced frustration from validation failures
- Transparent retry process via progress UI

---

### ADR-004: Floating-Only Panel (Sidebar Removed)

**Status**: Accepted (supersedes previous floating+sidebar decision)

#### Context
The initial design supported both floating and sidebar view modes. However, the floating panel with dynamic open/close and size expansion worked well as a standalone solution — it stays out of the way, doesn't conflict with other areas of Langflow (sidebar, playground, canvas), and the open/close/resize behavior feels natural. The sidebar mode added complexity (spacer divs, negative margins, conditional styling) for a view that wasn't needed.

#### Decision
Remove the sidebar view mode entirely. The assistant always uses the floating panel. Removed: view mode toggle, `AssistantViewMode` type, `useAssistantViewMode` hook, sidebar spacer div, and all sidebar-conditional CSS from FlowPage.

#### Consequences

**Benefits:**
- Simpler codebase — single layout to maintain
- No spacer divs or negative margins affecting the flow page
- Focused, polished experience for v1
- Resizable floating panel covers all use cases

**Trade-offs:**
- Users cannot dock the assistant to the side (can be revisited later if needed)

**Impact on Product:**
- Cleaner, more focused feature for initial release
- Faster iteration on a single well-polished layout

---

### ADR-005: Frontend-Owned Session Persistence

**Status**: Accepted

#### Context
The assistant had no conversation memory — every message was treated as a new session because the frontend never sent a `session_id`. The backend generated a new UUID per request (`request.session_id or str(uuid.uuid4())`), so the Agent's memory component never found previous messages.

#### Decision
The frontend generates a `session_id` once (via `useRef`) when the `useAssistantChat` hook initializes, and includes it in every `postAssistStream` request. A new `session_id` is only generated when the user clicks "New session" (`handleClearHistory`).

#### Consequences

**Benefits:**
- Conversation memory works across follow-up messages
- Users can iterate on component designs within a session
- "New session" provides a clean slate when needed

**Trade-offs:**
- Session memory is only frontend-scoped (lost on page refresh)
- Long sessions accumulate message history that may affect LLM context

**Key Files:**
- `src/frontend/.../hooks/use-assistant-chat.ts` — `sessionIdRef` stores the ID, passed in every request
- `src/backend/.../agentic/api/router.py` — falls back to `uuid.uuid4()` only if no `session_id` is sent

---

### ADR-006: TranslationFlow Session Isolation

**Status**: Accepted

#### Context
The TranslationFlow (intent classification) and LangflowAssistant flow shared the same `session_id`. This caused cross-flow contamination: the TranslationFlow's JSON intent responses were stored alongside the assistant's messages. On subsequent requests, the TranslationFlow's LLM saw messages from both flows in its history, causing intent classification to fail and default to `"question"`.

#### Decision
1. Pass `session_id=None` when calling `classify_intent` — the TranslationFlow is stateless and does not need conversation memory.
2. Set `should_store_message=False` on both ChatInput and ChatOutput in the TranslationFlow — it should never persist messages.

#### Consequences

**Benefits:**
- Intent classification is stateless and deterministic per message
- No cross-flow contamination in the assistant's message history
- TranslationFlow works identically on 1st and Nth request

**Trade-offs:**
- TranslationFlow has no context about previous turns (addressed by improved prompt, see ADR-007)

**Key Files:**
- `src/backend/.../agentic/services/assistant_service.py` — `session_id=None` in `classify_intent` call
- `src/backend/.../agentic/flows/translation_flow.py` — `should_store_message=False`

---

### ADR-007: Q&A Path Isolation and Off-Topic Guardrails (supersedes previous intent-independent extraction)

**Status**: Accepted

#### Context
The original ADR-007 introduced intent-independent code extraction: all responses were scanned for component code regardless of intent. This caused a critical bug: when users asked questions like "how do I create a component?", the LLM's example code in the answer was extracted, validated, and displayed as a component card instead of the text answer.

Additionally, the TranslationFlow only classified two intents (`generate_component` and `question`), allowing questions about unrelated tools (n8n, Docker, etc.) to pass through as `"question"` and receive full LLM responses.

#### Decision
Three changes:

1. **Q&A path isolation** — When intent is `"question"`, the backend returns the response immediately as plain text without code extraction/validation. Code extraction only runs for `"generate_component"` intent.

2. **Off-topic intent** — Added `"off_topic"` as a third intent classification. Questions about other tools, platforms, or unrelated topics are blocked before calling the main LLM, saving API cost and enforcing scope.

3. **Frontend fallback scoping** — The frontend only shows a component card for Q&A responses if `message.completedSteps` contains component generation steps (indicating the backend intended to generate a component). This prevents example code in explanatory answers from being misinterpreted.

#### Consequences

**Benefits:**
- Q&A answers with example code render as markdown, not component cards
- Off-topic questions are blocked before the expensive LLM call
- Clear separation between generation and Q&A paths

**Trade-offs:**
- If intent classification misses a follow-up modification (classifies as "question"), the component card won't appear. Mitigated by improved TranslationFlow prompt with modification examples.

**Key Files:**
- `src/backend/.../agentic/services/assistant_service.py` — `if not is_component_request: yield complete; return`
- `src/backend/.../agentic/flows/translation_flow.py` — three intents: `generate_component`, `question`, `off_topic`
- `src/frontend/.../components/assistant-message.tsx` — fallback scoped by `completedSteps`

---

### ADR-008: Fixed-Width Zoom Percentage Display

**Status**: Accepted

#### Context
The zoom percentage in the canvas controls bar (e.g., "65%", "150%", "200%") caused the entire controls bar to shift width when the zoom changed between values with different character counts. This created a visually distracting layout jump.

#### Decision
Apply a fixed width (`w-11`, 44px) with `text-center` to the zoom percentage display. Reduce the button's outer padding (`px-0.5`) to remove dead space between the redo icon and the percentage, and add `gap-0.5` between the percentage text and the chevron icon.

#### Key Files:
- `src/frontend/.../canvasControlsComponent/CanvasControlsDropdown.tsx` — fixed-width zoom display

---

### ADR-009: GPU-Accelerated Panel Open Transition

**Status**: Accepted

#### Context
Opening the assistant panel felt sluggish when there were previous chat messages. The root cause was `transition-all duration-300` on the panel container, which forced the browser to transition every CSS property (including height, width, border, shadow) across the entire message DOM on every open/close.

#### Decision
1. Replace `transition-all` with `transition-[opacity,transform]` — only animate the two properties needed for the fade+slide effect.
2. Reduce `duration-300` to `duration-200` for a snappier feel.
3. Add `will-change-[opacity,transform]` to hint the browser to GPU-accelerate these properties, avoiding expensive repaints on the message list.

#### Consequences

**Benefits:**
- Panel opens instantly regardless of message count
- No layout thrashing from transitioning height/width/shadow/border
- GPU-composited animation avoids main-thread repaints

**Trade-offs:**
- Size changes (compact → expanded) are no longer animated (they snap instantly, which is actually preferable)

**Key Files:**
- `src/frontend/.../assistantPanel/assistant-panel.tsx` — `containerClasses` transition properties

---

### ADR-010: Two-Phase Validation (Static + Runtime)

**Status**: Accepted

#### Context
The original validation (`validate_component_code`) only performed static AST analysis — syntax, class name extraction, overlapping I/O names, return statements. Code with valid syntax but wrong imports (e.g., `from lfx.base import Component` instead of `from lfx.custom import Component`) passed validation, was marked as `validated: true`, and showed "Add to Canvas". Clicking it failed silently because the `/api/v1/custom_component` endpoint performed real instantiation.

#### Decision
Add a second validation phase (`validate_component_runtime`) that attempts to instantiate the component using `Component(_code=code)` + `build_custom_component_template()`. If runtime validation fails, the error is fed back into the retry loop.

#### Consequences

**Benefits:**
- Components marked as `validated: true` can always be added to canvas
- Import errors, missing base classes, and runtime issues are caught during generation
- The retry loop includes runtime error context, improving LLM's ability to self-correct

**Trade-offs:**
- Runtime validation executes the generated code (mitigated by prior security scan)
- Slightly slower validation per attempt (~100ms overhead)

**Key Files:**
- `src/backend/.../agentic/helpers/validation.py` — `validate_component_runtime()`
- `src/backend/.../agentic/services/assistant_service.py` — calls runtime validation after AST passes

---

### ADR-011: Session ID Isolation from Playground

**Status**: Accepted

#### Context
Assistant sessions appeared in the Playground's session list because both used the same `MessageTable` with the same `flow_id`. The Assistant's `ChatOutput` component stored messages with `should_store_message=True`, and the Playground queried `SELECT DISTINCT session_id FROM message WHERE flow_id = ?`.

#### Decision
1. Prefix all Assistant session IDs with `agentic_` on the frontend.
2. Filter out `agentic_`-prefixed sessions in the Playground's session query.

#### Consequences

**Benefits:**
- Assistant sessions are completely invisible in the Playground
- Agent's conversation memory still works (same prefixed session_id across turns)
- No database schema changes required

**Key Files:**
- `src/frontend/.../hooks/use-assistant-chat.ts` — `AGENTIC_SESSION_PREFIX`
- `src/backend/.../api/v1/monitor.py` — `WHERE session_id NOT LIKE 'agentic_%'`

---

### ADR-012: Configurable Keyboard Shortcut

**Status**: Accepted

#### Context
The "A" key shortcut to open the assistant was hardcoded in `FlowPage/index.tsx`, making it impossible for users to remap or disable via Settings > Shortcuts.

#### Decision
Register the shortcut in the existing `customDefaultShortcuts` system with name "AI Assistant" and default key "a". The `FlowPage` reads the shortcut from `useShortcutsStore` instead of using a hardcoded string.

**Key Files:**
- `src/frontend/.../customization/constants.ts` — `"AI Assistant"` entry
- `src/frontend/.../stores/shortcuts.ts` — `aiAssistant: "a"`
- `src/frontend/.../pages/FlowPage/index.tsx` — reads from store

---

### ADR-013: Resilient Intent Classification for Diverse Models

**Status**: Accepted

#### Context
Models like IBM granite return non-JSON responses from the TranslationFlow, causing all requests to default to `"question"` intent. This prevented component generation from ever triggering with these models.

#### Decision
Add three progressive fallbacks when `json.loads()` fails:
1. Extract JSON from markdown code blocks (`` ```json ... ``` ``)
2. Find JSON objects embedded in surrounding text
3. Match known intent keywords in plain text (`"generate_component"`, `"off_topic"`)

**Key Files:**
- `src/backend/.../services/helpers/intent_classification.py` — `_MARKDOWN_JSON_RE`, `_EMBEDDED_JSON_RE`, keyword fallback

---

### ADR-014: Provider-Specific Parameter Injection

**Status**: Accepted

#### Context
IBM WatsonX and Ollama require additional parameters beyond API key and model name (WatsonX: URL + project ID; Ollama: base URL). The `inject_model_into_flow` function only injected the `model` value into Agent nodes, leaving provider-specific fields empty. This caused authentication failures for WatsonX in the Assistant.

#### Decision
Thread `provider_vars` (resolved from database) through `flow_executor` → `flow_loader` → `inject_model_into_flow`. The injection function now sets `api_key`, `base_url_ibm_watsonx`, `project_id` (WatsonX) and `base_url_ollama` (Ollama) on Agent node templates.

**Key Files:**
- `src/backend/.../services/flow_preparation.py` — `provider_fields` injection
- `src/backend/.../services/flow_executor.py` — passes `global_variables` as `provider_vars`

---

### ADR-015: Session Storage in localStorage (Not Database)

**Status**: Accepted

#### Context
Users expect assistant session history to persist. A decision was needed on whether to store sessions in the database (like the Playground) or in browser localStorage.

#### Decision
Session history is stored in browser `localStorage` (key: `langflow-assistant-sessions`), limited to 10 sessions. Sessions are serialized/deserialized with `progress` state stripped and in-flight messages marked as `"cancelled"`.

#### Consequences

**Benefits:**
- Zero backend changes — no new API endpoints or database tables
- Fast read/write with no network latency
- Simple implementation matching the frontend-scoped session_id model

**Trade-offs:**
- **Sessions are lost when browser cache is cleared** — users should be aware
- No cross-device or cross-browser synchronization
- Limited to 10 sessions (oldest dropped on overflow)
- Session data is not backed up or recoverable

**Important: This is a known limitation.** If users report lost sessions, the answer is that assistant sessions are browser-local only. Database persistence can be added as a future enhancement if needed.

**Key Files:**
- `src/frontend/.../hooks/use-session-history.ts` — `saveCurrentSession()`, `switchSession()`, `deleteSession()`
- `src/frontend/.../helpers/session-storage.ts` — serialization/deserialization
- `src/frontend/.../assistant-panel.constants.ts` — `ASSISTANT_SESSIONS_STORAGE_KEY`, `ASSISTANT_MAX_SESSIONS`

---

### ADR-016: Single-Agent-Loop over Multi-Phase Orchestration

**Status**: Accepted (supersedes the multi-phase orchestrator approach)

#### Context
The assistant had grown into a multi-phase orchestrator with separate sub-agents per phase. This added coordination overhead, divergent prompts, and made compound requests ("make a component, build a flow with it, and run it") brittle. Tools like Claude Code and Codex demonstrate that a single agent with a good toolkit handles multi-step work more reliably.

#### Decision
Collapse the assistant into ONE agent (`flow_builder_assistant.py`) plus an MCP toolkit (`src/lfx/src/lfx/mcp/flow_builder_tools.py`). Single-thing requests behave exactly as before (byte-identical experience). When the user asks for multiple things in one prompt, the SAME single loop chains the tools (orchestration) — no separate sub-agents are spawned.

#### Consequences

**Benefits:**
- One prompt, one loop — simpler to reason about and to evolve
- Compound requests handled natively by tool chaining
- No cross-sub-agent state divergence

**Trade-offs:**
- The single prompt must encode targeting/self-verification discipline (see ADR-021)
- Long tool chains accumulate context within one loop

**Key Files:**
- `src/backend/.../agentic/flows/flow_builder_assistant.py` — the single agent
- `src/lfx/src/lfx/mcp/flow_builder_tools.py` — `GenerateComponent`, `DescribeFlowIO`, `RunFlow`
- `src/backend/base/langflow/agentic/ARCHITECTURE.md` — end-to-end diagrams

---

### ADR-017: Provider-Agnostic In-Flow Model Selection

**Status**: Accepted (clarifies/supersedes the provider-preference part of ADR-014 and the §3 "Model Selection Behavior" / `ModelProviderConfiguration` provider-preference invariant)

#### Context
The §3 `ModelProviderConfiguration` invariant and the "Model Selection Behavior" note state a hard preference order "Anthropic > OpenAI > Google Generative AI > Groq" and imply a provider fallback obligation for the *in-flow Agent model*. In practice, forcing a fixed order (especially an OpenAI obligation) fails when only a different provider has a configured key.

#### Decision
`available_model_providers(global_variables)` in `agentic/services/flow_preparation.py` detects providers that actually have a configured key. The prompt injects an `[Available language models ...]` block and forbids running an Agent that has no model.

Clarification of the older text (the original text is intentionally **not deleted**): the *assistant's own* model is preferred when available; for the **flow's Agent node**, any provider with a configured key may be used — there is **no fixed OpenAI/Anthropic obligation** and no fixed provider-preference order.

#### Consequences

**Benefits:**
- Works with any single configured provider (no OpenAI requirement)
- The Agent node is never wired without a usable model
- Prompt is grounded in the user's real provider configuration

**Trade-offs:**
- Model choice for the flow's Agent is less deterministic across users

**Key Files:**
- `src/backend/.../agentic/services/flow_preparation.py` — `available_model_providers()`

---

### ADR-018: Optional propose_plan

**Status**: Accepted

#### Context
Previously the agent stopped for a plan card on essentially every flow build, which slowed down small/unambiguous edits and added an extra approval round-trip.

#### Decision
`propose_plan` is now OPTIONAL. The agent only stops for a plan card on large or ambiguous changes; small unambiguous changes are applied directly. Plan approval still uses the byte-identical `PLAN_APPROVAL_INPUT` protocol string (matched exactly, bypassing the classifier).

#### Consequences

**Benefits:**
- Faster path for routine edits
- Plan card reserved for cases where it actually adds value

**Trade-offs:**
- Heuristic decides "large/ambiguous"; occasional mismatch with user expectation

---

### ADR-019: Run Metrics Extraction

**Status**: Accepted

#### Context
After the assistant runs a flow, users want to know how long it took and how many tokens it consumed. Earlier "run visual feedback" UI added complexity without surfacing concrete numbers.

#### Decision
`RunFlow` returns `{duration_seconds, input_tokens, output_tokens, total_tokens}`. Duration is measured with `perf_counter`; tokens are aggregated via `extract_graph_token_usage` over the graph vertices (`agentic/services/flow_run.py`). All "run visual feedback" code was removed — only run + result + metrics remain.

#### Consequences

**Benefits:**
- Accurate, comparable duration (monotonic clock, not wall-clock)
- Token usage is read from the actual graph vertices, not estimated
- Simpler surface (no separate run-feedback UI)

**Trade-offs:**
- Token counts depend on vertices exposing usage; components that don't report usage contribute zero

**Key Files:**
- `src/backend/.../agentic/services/flow_run.py` — `perf_counter` duration, `extract_graph_token_usage`

---

### ADR-020: Edit + Run Continuation Gating

**Status**: Accepted (extends ADR for assistant edit-approval continuation)

#### Context
When the user approves proposed canvas edits, deferred steps (e.g., running the flow) must still complete on the SAME request. An earlier implementation re-sent the continuation unconditionally, causing a duplicate-message glitch when there was nothing deferred.

#### Decision
After approval the frontend saves the flow, then silently re-sends `EDIT_CONTINUATION_INPUT` (byte-identical FE/BE protocol string, matched exactly, bypassing the classifier) so the same request finishes deferred steps. `configure_component` direct-apply now runs in the same turn. Continuation only fires if a deferred step actually existed, gated by `continuation_expected`.

#### Consequences

**Benefits:**
- Deferred run completes seamlessly after edit approval
- No duplicate assistant message when nothing was deferred

**Trade-offs:**
- Frontend and backend must keep the protocol string byte-identical

---

### ADR-021: Real Introspection for User Component Overlay & In-Place Working-Flow ContextVar

**Status**: Accepted

#### Context
The user component overlay scaffolded outputs by guessing, causing run crashes like "Attribute build_output not found" and wrong-output scaffolds. Separately, `build_flow` rebinding the working-flow ContextVar via `.set()` meant the run engine did not see the canvas ("There is no flow on the canvas to run").

#### Decision
1. The overlay now does REAL introspection via `build_custom_component_template(Component(_code=code))` (`agentic/services/user_components_overlay.py`), reflecting the class's real `Output` method (AST-derived).
2. `build_flow` mutates the working-flow ContextVar IN PLACE (never `.set()` rebind) so the run engine sees the canvas. New ContextVars: `agent_run_context` (provider/model/api_key_var) and `_current_flow_id_var`.
3. The prompt has an explicit targeting rule (act on the right component) plus self-verification after acting.

#### Consequences

**Benefits:**
- Fixes "Attribute build_output not found" and wrong-output scaffolds
- Run engine reliably sees the freshly built flow
- Agent acts on the intended component and verifies its own actions

**Key Files:**
- `src/backend/.../agentic/services/user_components_overlay.py` — real introspection
- `src/backend/.../agentic/services/agent_run_context.py` — `agent_run_context`, `_current_flow_id_var`

---

### ADR-022: Frontend — Replace-Canvas fitView & Edit Diff Card Readability

**Status**: Accepted

#### Context
"Replace canvas" left the new flow off-screen, and the flow-edit diff card was hard to read (raw `\n`, missing "Show more", misaligned Accept/Dismiss).

#### Decision
1. `Replace canvas` performs a proper `fitView` via a double `requestAnimationFrame` (`apply-flow-update.ts`).
2. The flow-edit diff card renders without raw `\n`, restores "Show more", and aligns Accept/Dismiss to the GHOST green button pattern used by the other cards.

#### Consequences

**Benefits:**
- Replaced flow is visible and framed immediately
- Diff card is readable and visually consistent with sibling cards

**Key Files:**
- `src/frontend/.../apply-flow-update.ts` — double-rAF `fitView`

---

## 6. Technical Specification

### 6.1 Dependencies

| Type | Name | Purpose |
|------|------|---------|
| Service | `FlowExecutor` | Executes pre-built assistant flows (.py or .json, with .py taking priority) |
| Service | `ProviderService` | Detects configured model providers and retrieves API keys |
| Service | `VariableService` | Retrieves user's stored API keys from encrypted storage |
| Service | `ValidationService` | Compiles and instantiates component code for validation |
| External API | LLM Provider APIs | OpenAI, Anthropic, Azure, Google, IBM WatsonX, Ollama, Groq - for text generation |
| Library | `lfx.run` | Flow execution engine |
| Library | `lfx.custom.validate` | Component class creation and validation |
| Frontend | `use-stick-to-bottom` | Auto-scroll behavior in chat |
| Frontend | `@xyflow/react` | Canvas integration for component placement |

### 6.2 API Contracts

#### POST /api/v1/agentic/assist/stream

**Purpose**: Generate component or answer question with streaming progress updates

**Request**:
```json
{
  "flow_id": "string - Required. UUID of the current flow",
  "input_value": "string - The user's message/prompt",
  "provider": "string - Optional. Model provider (openai, anthropic, etc.)",
  "model_name": "string - Optional. Specific model name (gpt-4o, claude-3-opus, etc.)",
  "max_retries": "integer - Optional. Total validation attempts (default: 3)",
  "session_id": "string - Required for conversation memory. Prefixed with 'agentic_' to isolate from Playground. Generated once per session by the frontend, reused across all requests. New ID on 'New session' only. Backend falls back to uuid4() if omitted."
}
```

**Response (SSE Stream)**:

Event: `progress`
```json
{
  "event": "progress",
  "step": "generating_component | generating | extracting_code | validating | validated | validation_failed | retrying | orchestrating",
  "attempt": 0,
  "max_attempts": 3,
  "message": "string - Human-readable status message",
  "error": "string - Optional. Error message for validation_failed",
  "class_name": "string - Optional. Component class name",
  "component_code": "string - Optional. Generated code for validation_failed"
}
```

Event: `token` (Q&A only)
```json
{
  "event": "token",
  "chunk": "string - Token text"
}
```

Event: `complete`
```json
{
  "event": "complete",
  "data": {
    "result": "string - Full response text",
    "validated": true,
    "class_name": "UppercaseComponent",
    "component_code": "class UppercaseComponent(Component):...",
    "validation_attempts": 1,
    "continuation_expected": "boolean - Optional. True when a deferred step exists and the frontend should silently re-send EDIT_CONTINUATION_INPUT after saving the flow",
    "run_metrics": {
      "duration_seconds": "number - Optional. perf_counter-measured run duration (present when RunFlow executed)",
      "input_tokens": "integer - Optional. Aggregated via extract_graph_token_usage over graph vertices",
      "output_tokens": "integer - Optional.",
      "total_tokens": "integer - Optional."
    }
  }
}
```

Event: `error`
```json
{
  "event": "error",
  "message": "string - Friendly error message"
}
```

Event: `cancelled`
```json
{
  "event": "cancelled",
  "message": "string - Optional cancellation reason"
}
```

---

#### GET /api/v1/agentic/check-config

**Purpose**: Check if assistant is properly configured and return available providers

**Request**: None (uses authenticated user context)

**Response (Success)**:
```json
{
  "configured": true,
  "configured_providers": ["openai", "anthropic"],
  "providers": [
    {
      "name": "openai",
      "configured": true,
      "default_model": "gpt-4o",
      "models": [
        {"name": "gpt-4o", "display_name": "GPT-4o"},
        {"name": "gpt-4-turbo", "display_name": "GPT-4 Turbo"}
      ]
    }
  ],
  "default_provider": "openai",
  "default_model": "gpt-4o"
}
```

---

#### POST /api/v1/agentic/assist

**Purpose**: Non-streaming version of assist (prefer streaming for better UX)

**Request**: Same as `/assist/stream`

**Response (Success)**:
```json
{
  "result": "string - Full response",
  "validated": true,
  "class_name": "MyComponent",
  "component_code": "string - Python code",
  "validation_attempts": 1
}
```

### 6.3 Error Handling

| Error Code | Condition | User Message | Recovery Action |
|------------|-----------|--------------|-----------------|
| `400` | No provider configured | "No model provider is configured. Please configure at least one model provider in Settings." | Navigate to Settings > Model Providers |
| `400` | Provider not available | "Provider 'X' is not configured. Available providers: [list]" | Select a different provider or configure the requested one |
| `400` | Missing API key | "OPENAI_API_KEY is required for the Langflow Assistant with openai. Please configure it in Settings > Model Providers." | Add API key in Settings |
| `400` | Unknown provider | "Unknown provider: X" | Use a supported provider |
| `404` | Flow file not found | "Flow file 'X.json' not found" | Ensure agentic flows are deployed |
| `500` | Flow execution error | Friendly error extracted from the actual error (e.g., "Rate limit exceeded. Please wait a moment and try again.") | Retry request; check server logs |
| `ValidationError` | Code syntax error | Includes `SyntaxError: ...` | System auto-retries with error context |
| `ValidationError` | Import error | Includes `ModuleNotFoundError: ...` | System auto-retries with error context |
| `ValidationError` | Missing Component base | "Could not extract class name from code" | System auto-retries with hint |
| `NetworkError` | Client disconnected | "Request cancelled" | User can retry |

---

## 7. Observability

### 7.1 Key Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `assistant_requests_total` | Counter | Total number of assistant requests | N/A (baseline) |
| `assistant_requests_by_intent` | Counter | Requests segmented by intent (generate_component, question, off_topic) | N/A |
| `assistant_generation_duration_seconds` | Histogram | Time from request to completion | P95 > 60s |
| `assistant_validation_attempts` | Histogram | Number of validation attempts per request | P95 > 2 |
| `assistant_validation_success_rate` | Gauge | Percentage of validations succeeding on first attempt | < 70% |
| `assistant_provider_usage` | Counter | Requests by provider (openai, anthropic, etc.) | N/A |
| `assistant_errors_total` | Counter | Total errors by type | > 10/min |
| `assistant_cancellations_total` | Counter | User-initiated cancellations | > 20% of requests |

### 7.2 Important Logs

| Log Level | Event | Fields | When |
|-----------|-------|--------|------|
| `INFO` | `assistant.request.started` | `user_id`, `flow_id`, `provider`, `model_name`, `intent` | Request received |
| `INFO` | `assistant.generation.attempt` | `attempt`, `max_retries` | Each generation attempt |
| `INFO` | `assistant.validation.success` | `class_name`, `attempts` | Component validated successfully |
| `WARNING` | `assistant.validation.failed` | `error`, `attempt`, `class_name` | Validation failed, will retry |
| `ERROR` | `assistant.validation.exhausted` | `error`, `attempts`, `code_snippet` | Max retries reached |
| `INFO` | `assistant.request.completed` | `duration_ms`, `validated`, `attempts` | Request finished |
| `INFO` | `assistant.request.cancelled` | `reason`, `duration_ms` | User cancelled |
| `ERROR` | `assistant.flow.error` | `error_type`, `error_message`, `flow_name` | Flow execution failed |

### 7.3 Dashboards

**Assistant Usage Dashboard:**
- Request Rate - Requests per minute over time
- Intent Distribution - Pie chart of generate_component vs question vs off_topic
- Provider Usage - Bar chart of requests by provider
- Validation Success Rate - Time series of first-attempt success rate
- Response Time P50/P95/P99 - Latency distribution

**Assistant Health Dashboard:**
- Error Rate by Type - Stacked area chart
- Provider Availability - Status indicators per provider
- Validation Failure Reasons - Top error messages
- Stream Disconnect Rate - Client disconnects over time

---

## 8. Deployment & Rollback

### 8.1 Feature Flags

No dedicated feature flags are currently implemented. The assistant is always enabled when the agentic backend is available. Feature flags may be added in the future for granular control.

### 8.2 Database Migrations

- No database migrations required
- Configuration stored in existing `variables` table (API keys)
- Session messages are persisted in the message store (keyed by `session_id`) for Agent conversation memory within a session
- Session ID is frontend-scoped, prefixed with `agentic_`, and generated per hook instance (reset on "New session")
- **Session history (chat messages list) is stored in browser `localStorage` only** — not in the database. Clearing browser data deletes all assistant session history. This is by design (see ADR-015)
- The Playground filters out `agentic_`-prefixed sessions to avoid cross-contamination (see ADR-011)

### 8.3 Rollback Plan

1. **Immediate**: Set `assistant_enabled` feature flag to `off`
2. **If backend issues**: Revert backend deployment to previous version
3. **If frontend issues**: Revert frontend deployment to previous version
4. **Data considerations**: No persistent data to rollback
5. **Dependencies**: No downstream dependencies affected

### 8.4 Smoke Tests

- [ ] Open assistant panel from canvas controls
- [ ] Verify model providers are detected (if configured)
- [ ] Submit a simple component generation request
- [ ] Verify progress indicators appear during generation
- [ ] Verify component code is displayed on completion
- [ ] Click "Add to Canvas" and verify component appears
- [ ] Submit a Q&A question and verify streaming response
- [ ] Submit a follow-up modification (e.g., "use dataframe output instead") and verify the progress card appears (not raw code)
- [ ] Verify conversation memory: ask a follow-up that references the previous component
- [ ] Click "New session" and verify the assistant does not remember the previous conversation
- [ ] Cancel a generation in progress
- [ ] Clear conversation history
- [ ] Press the configured shortcut (default **A**) on the canvas to open the assistant and verify the input is auto-focused
- [ ] Press **Escape** to close the assistant (from both canvas and input focus)
- [ ] Verify the shortcut is listed and editable in Settings > Shortcuts
- [ ] Verify the input placeholder shows "Working on it..." during generation (not a random suggestion)
- [ ] Resize the floating panel by dragging edges and verify size is persisted
- [ ] Verify zoom percentage display doesn't shift the controls bar when zooming between 60% and 200%
- [ ] Open the assistant panel with previous messages and verify it opens instantly (no lag)
- [ ] Verify assistant sessions do NOT appear in Playground session list
- [ ] Ask an off-topic question (e.g., "how does n8n work?") and verify it is blocked
- [ ] Verify model selector shows correct provider icon (not generic "AI")
- [ ] Switch to a different provider and verify the icon updates
- [ ] Generate a component with invalid imports and verify retry loop catches it with runtime validation
- [ ] Verify validation failure shows friendly message with collapsible error details
- [ ] Verify attempt counter shows correct "Attempt X of 3" (never exceeds max)
- [ ] Test with IBM WatsonX or Ollama provider and verify it works
- [ ] Submit a compound prompt ("create a component, build a flow with it, and run it") and verify the single loop chains the tools and returns a run result
- [ ] Configure ONLY a non-OpenAI provider and verify a flow's Agent node is wired with that provider (no forced OpenAI/Anthropic)
- [ ] Run a flow and verify run metrics (duration_seconds + token counts) are shown after completion
- [ ] Approve proposed canvas edits with a deferred run and verify it continues on the same request (no duplicate message); verify no continuation fires when nothing was deferred
- [ ] Use "Replace canvas" and verify the new flow is framed via fitView (visible, not off-screen)
- [ ] Verify a multi-step prompt shows the "Orchestrating..." progress label

---

## 9. Architecture Diagrams

### 9.1 Context Diagram (Level 1)

```mermaid
C4Context
  title System Context diagram for Langflow Assistant

  Person(user, "Langflow User", "Builds AI workflows using visual canvas")

  System(assistant, "Langflow Assistant", "AI-powered component generation through natural language")

  System_Ext(llm_providers, "LLM Providers", "OpenAI, Anthropic, Azure, Google - text generation")
  System_Ext(langflow_core, "Langflow Core", "Flow execution, component validation, canvas")

  Rel(user, assistant, "Sends prompts, receives components")
  Rel(assistant, llm_providers, "Generates text via API")
  Rel(assistant, langflow_core, "Validates code, adds to canvas")
```

### 9.2 Container Diagram (Level 2)

```mermaid
C4Container
  title Container diagram for Langflow Assistant

  Person(user, "User", "Langflow user")

  Container_Boundary(frontend, "Frontend") {
    Container(assistant_panel, "AssistantPanel", "React", "Chat UI with progress indicators")
    Container(assistant_hooks, "Assistant Hooks", "React Hooks", "State management and API calls")
    Container(sse_client, "SSE Client", "TypeScript", "Parses streaming events")
  }

  Container_Boundary(backend, "Backend") {
    Container(agentic_api, "Agentic API", "FastAPI", "HTTP endpoints for assistant")
    Container(assistant_service, "AssistantService", "Python", "Orchestrates generation with retry")
    Container(flow_executor, "FlowExecutor", "Python", "Runs assistant flows")
    Container(validation_service, "ValidationService", "Python", "Validates component code")
  }

  Container_Ext(flows, "Assistant Flows", "JSON/Python", "LangflowAssistant.json, translation_flow.py")
  System_Ext(llm, "LLM Provider", "External API")

  Rel(user, assistant_panel, "Enters prompts")
  Rel(assistant_panel, assistant_hooks, "Uses")
  Rel(assistant_hooks, sse_client, "Processes stream")
  Rel(sse_client, agentic_api, "POST /assist/stream", "SSE")
  Rel(agentic_api, assistant_service, "Delegates")
  Rel(assistant_service, flow_executor, "Executes flows")
  Rel(assistant_service, validation_service, "Validates code")
  Rel(flow_executor, flows, "Loads")
  Rel(flow_executor, llm, "Calls API")
```

### 9.3 Component Flow Diagram

> **Note (2026-05-19):** the pipeline is now a single agent loop
> (`flow_builder_assistant.py`) plus an MCP toolkit
> (`GenerateComponent`, `DescribeFlowIO`, `RunFlow`). The diagram below still
> describes the feature-level intent → generate → validate → run flow (which is
> byte-identical for single-thing requests); for multi-thing/compound prompts
> the SAME loop chains the tools. The full single-agent-loop + MCP wiring
> diagrams live in `src/backend/base/langflow/agentic/ARCHITECTURE.md` — the
> existing diagrams here are intentionally left as-is.

```mermaid
flowchart TD
    A[User Input] --> B{Intent Classification<br/>TranslationFlow - stateless}
    B -->|off_topic| Z[Return Refusal Message<br/>no LLM call]
    B -->|generate_component| C[Execute LangflowAssistant Flow]
    B -->|question| D[Execute LangflowAssistant Flow<br/>with token streaming]

    D --> F[Complete Response<br/>plain text / Q&A]

    C --> G[Extract Component Code]

    G --> H{Code Found?}
    H -->|No| F
    H -->|Yes| I[Static Validation<br/>AST parsing]

    I --> I2{AST Valid?}
    I2 -->|No| L
    I2 -->|Yes| I3[Runtime Validation<br/>instantiate component]

    I3 --> J{Runtime Valid?}
    J -->|Yes| K[Return Validated Component<br/>component card with Add to Canvas]
    J -->|No| L{Retries Left?}

    L -->|Yes| M[Retry with Error Context]
    M --> C
    L -->|No| N[Return Friendly Error<br/>collapsible details + Try Again]

    K --> O[User Clicks Add to Canvas]
    O --> P[Component API Validation]
    P --> Q[Add to Canvas]
```

### 9.4 State Machine: Generation Pipeline

```
┌──────────┐    ┌─────────────────────────┐
│  Start   │───▶│  Intent Classification  │
└──────────┘    └─────────┬───────────────┘
                          │
              ┌───────────┼────────────┐
              │           │            │
              ▼           ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌────────────┐
        │off_topic │ │ question │ │gen_component│
        └────┬─────┘ └────┬─────┘ └─────┬──────┘
             │            │              │
             ▼            ▼              ▼
        ┌──────────┐ ┌──────────┐ ┌────────────────────────┐
        │ refusal  │ │generating│ │  generating_component  │
        │ message  │ └────┬─────┘ └─────────┬──────────────┘
        └──────────┘      │                 │
                          ▼                 ▼
                   ┌────────────┐    ┌─────────────────┐
                   │  complete  │    │generation_complete│
                   │(plain text)│    └────────┬────────┘
                   └────────────┘             │
                                              ▼
                                     ┌─────────────────┐
                                     │ extracting_code │
                                     └────────┬────────┘
                                              │
                                     ┌────────▼────────┐
                                     │   validating    │
                                     │ (AST + Runtime) │
                                     └────────┬────────┘
                                              │
                          ┌───────────────────┼────────────────┐
                          │ Valid             │ Invalid        │
                          ▼                   ▼                │
                 ┌─────────────────┐ ┌──────────────────────┐  │
                 │    validated    │ │  validation_failed   │  │
                 └────────┬────────┘ └──────────┬───────────┘  │
                          │                     │              │
                          ▼                     ▼              │
                 ┌─────────────────┐   ┌─────────────────┐    │
                 │    complete     │   │    retrying     │────┘
                 │   (validated)   │   └─────────────────┘
                 └─────────────────┘          │
                                              │ max attempts
                                              ▼
                                     ┌─────────────────┐
                                     │    complete     │
                                     │ (not validated) │
                                     │ friendly error  │
                                     └─────────────────┘
```
