from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from lfx.log.logger import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.workflow_edit_tools import WORKFLOW_MCP_TOOLS, WorkflowEditError, call_workflow_tool
from langflow.services.deps import get_variable_service, session_scope

router = APIRouter(prefix="/flow-assistant", tags=["Flow Assistant"])

QUERYROUTER_BASE_URL = "https://api.queryrouter.ru/v1"
FLOW_ID_REQUIRED_TOOL_NAMES: set[str] = {
    t.name for t in WORKFLOW_MCP_TOOLS if "flow_id" in (t.input_schema.get("required") or [])
}


def _get_max_iterations() -> int:
    """Get max iterations for assistant tool loop. 0 means unlimited."""
    try:
        value = int(os.getenv("LANGFLOW_FLOW_ASSISTANT_MAX_ITERATIONS", "0"))
        return max(0, value)
    except ValueError:
        return 0


def _new_tool_call_id() -> str:
    return f"call_{uuid4().hex}"


def _ensure_tool_call_ids(tool_calls: list[dict[str, Any]]) -> None:
    for tc in tool_calls:
        if not tc.get("id"):
            tc["id"] = _new_tool_call_id()


def _maybe_inject_flow_id(*, tool_name: str, tool_args: dict[str, Any], flow_id: UUID) -> dict[str, Any]:
    if tool_name not in FLOW_ID_REQUIRED_TOOL_NAMES:
        return tool_args
    if tool_args.get("flow_id"):
        return tool_args
    return {**tool_args, "flow_id": str(flow_id)}


def _is_complete_tool_call(tc: dict[str, Any]) -> bool:
    tc_func = tc.get("function")
    if not isinstance(tc_func, dict):
        return False
    name = tc_func.get("name")
    return isinstance(name, str) and bool(name.strip())


def _filter_complete_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [tc for tc in tool_calls if _is_complete_tool_call(tc)]


class AssistantMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def _validate_openai_tool_fields(self) -> AssistantMessage:
        if self.role == "tool" and not self.tool_call_id:
            raise _ToolCallIdRequiredForToolRoleError
        if self.role != "tool" and self.tool_call_id is not None:
            raise _ToolCallIdOnlyAllowedForToolRoleError
        if self.role != "assistant" and self.tool_calls is not None:
            raise _ToolCallsOnlyAllowedForAssistantRoleError
        if self.role == "assistant" and self.tool_calls is not None:
            for tc in self.tool_calls:
                if not isinstance(tc, dict):
                    raise _ToolCallsItemsMustBeObjectsError
                if not tc.get("id"):
                    raise _ToolCallsIdRequiredError
        return self


class _AssistantMessageValidationError(ValueError):
    """Base error for invalid OpenAI chat messages in Flow Assistant history."""


class _ToolCallIdRequiredForToolRoleError(_AssistantMessageValidationError):
    def __init__(self) -> None:
        super().__init__("tool_call_id is required when role='tool'")


class _ToolCallIdOnlyAllowedForToolRoleError(_AssistantMessageValidationError):
    def __init__(self) -> None:
        super().__init__("tool_call_id is only allowed when role='tool'")


class _ToolCallsOnlyAllowedForAssistantRoleError(_AssistantMessageValidationError):
    def __init__(self) -> None:
        super().__init__("tool_calls is only allowed when role='assistant'")


class _ToolCallsItemsMustBeObjectsError(_AssistantMessageValidationError):
    def __init__(self) -> None:
        super().__init__("tool_calls items must be objects")


class _ToolCallsIdRequiredError(_AssistantMessageValidationError):
    def __init__(self) -> None:
        super().__init__("tool_calls[].id is required for assistant messages")


def _normalize_tool_call_arguments(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize tool call payloads to OpenAI-compatible schema.

    OpenAI requires `function.arguments` to be a JSON string.
    """
    normalized: list[dict[str, Any]] = []
    for tc in tool_calls:
        tc_copy = dict(tc)
        tc_func = tc_copy.get("function")
        if isinstance(tc_func, dict):
            tc_func_copy = dict(tc_func)
            args = tc_func_copy.get("arguments")
            if isinstance(args, dict):
                tc_func_copy["arguments"] = json.dumps(args)
            tc_copy["function"] = tc_func_copy
        normalized.append(tc_copy)
    return normalized


def _assistant_message_to_openai_dict(m: AssistantMessage) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": m.role, "content": m.content or ""}
    if m.tool_calls is not None:
        msg["tool_calls"] = _normalize_tool_call_arguments(m.tool_calls)
    if m.tool_call_id is not None:
        msg["tool_call_id"] = m.tool_call_id
    return msg


def _build_openai_messages(*, flow_id: UUID, message: str, history: list[AssistantMessage]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": _system_prompt()}]
    messages.extend(_assistant_message_to_openai_dict(m) for m in history)
    messages.append({"role": "user", "content": f"flow_id={flow_id}\n\n{message}"})
    return messages


class ToolCallDetail(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None


class FlowAssistantChatRequest(BaseModel):
    flow_id: UUID
    message: str = Field(min_length=1)
    history: list[AssistantMessage] = Field(default_factory=list)
    model: str | None = None


class FlowAssistantChatResponse(BaseModel):
    message: str
    tool_calls: list[ToolCallDetail] = Field(default_factory=list)


def _get_queryrouter_api_key_from_env() -> str | None:
    env_key = os.getenv("QUERYROUTER_API_KEY", "").strip()
    if env_key and env_key != "dummy":
        return env_key
    return None


async def _get_queryrouter_api_key_for_user(*, user_id: UUID) -> str | None:
    async with session_scope() as session:
        variable_service = get_variable_service()
        try:
            key = await variable_service.get_variable(
                user_id=user_id,
                name="QUERYROUTER_API_KEY",
                field="queryrouter_api_key",
                session=session,
            )
            key = (key or "").strip()
            if key and key != "dummy":
                return key
        except Exception:  # noqa: BLE001
            return _get_queryrouter_api_key_from_env()
    return _get_queryrouter_api_key_from_env()


def _queryrouter_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def _fetch_queryrouter_models(api_key: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{QUERYROUTER_BASE_URL}/models", headers=_queryrouter_headers(api_key))
            resp.raise_for_status()
            data = resp.json().get("data", [])
            result: list[dict[str, Any]] = []
            for m in data:
                slug = m.get("slug") or m.get("id")
                if not slug:
                    continue
                result.append(
                    {
                        "slug": slug,
                        "name": m.get("display_name") or m.get("name", slug),
                        "context_length": m.get("context_length", 0),
                        "vendor": m.get("vendor") or m.get("owned_by", ""),
                        "model_type": m.get("model_type", "chat"),
                    }
                )
            return sorted(result, key=lambda x: x["name"])
    except Exception as exc:  # noqa: BLE001
        await logger.awarning(f"Failed to fetch QueryRouter models: {exc!s}")
        return []


@router.get("/models", status_code=200)
async def flow_assistant_models(current_user: CurrentActiveUser):
    api_key = await _get_queryrouter_api_key_for_user(user_id=current_user.id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QUERYROUTER_API_KEY not found. Set it as a Global Variable named QUERYROUTER_API_KEY.",
        )
    models = await _fetch_queryrouter_models(api_key)
    return {"models": models}


def _build_openai_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        for tool in WORKFLOW_MCP_TOOLS
    ]


def _system_prompt() -> str:
    return """You are a Langflow Workflow Assistant. Your job is to help create, modify, and debug the user's workflow.

═══════════════════════════════════════════════════════════════════════════════
CRITICAL: USE QueryRouter AS DEFAULT LLM PROVIDER
═══════════════════════════════════════════════════════════════════════════════
QueryRouter is the PREFERRED LLM provider for all workflows. It provides:
- Unified access to 100+ AI models (OpenAI, Anthropic, Google, DeepSeek, etc.)
- Single API key for all providers (QUERYROUTER_API_KEY)
- Automatic model selection with pricing info
- OpenAI-compatible API

Component: "QueryRouterModel" (display name: "QueryRouter")
Category: models (or use lf_get_component_info with "QueryRouterModel")

ALWAYS use QueryRouterModel instead of OpenAIModel, AnthropicModel, etc.
unless user explicitly requests a specific provider.

═══════════════════════════════════════════════════════════════════════════════
CRITICAL PRINCIPLE: PREFER STANDARD COMPONENTS OVER CUSTOM ONES
═══════════════════════════════════════════════════════════════════════════════
ALWAYS use lf_get_component_info to check if a standard component can solve the task
BEFORE creating a custom component. Langflow has 100+ built-in components covering:
- LLM providers (QueryRouter - recommended!, OpenAI, Anthropic, Google, Groq, Ollama)
- Data processing (Split, Parse, Combine, Filter, Transform)
- Vector stores (Pinecone, Chroma, Qdrant, Weaviate, etc.)
- Document loaders (PDF, CSV, JSON, Web scraping, etc.)
- Agents with tools and memory
- API integrations and webhooks

Custom components should be a LAST RESORT when no standard component exists.

═══════════════════════════════════════════════════════════════════════════════
AVAILABLE TOOLS
═══════════════════════════════════════════════════════════════════════════════

1. lf_workflow_get - Get current workflow state (nodes/edges)
   Returns optimized structure without source code to save tokens.

2. lf_check_workflow - CHECK WORKFLOW HEALTH (USE AFTER EVERY CHANGE!)
   Returns structured issues: disconnected nodes, missing required fields, type mismatches.
   ALWAYS call this after making changes to verify workflow correctness.

3. lf_get_component_info - GET COMPONENT DETAILS (USE BEFORE ADDING!)
   Returns: description, all inputs (with types, options, defaults), all outputs.
   ALWAYS use this to understand component capabilities before adding it.

4. lf_list_components - List component names by category.
   Categories: input_output, processing, openai, anthropic, google, agents, helpers,
   models, tools, data, logic, vectorstores, embeddings, memories, retrievers.

5. lf_workflow_patch - Apply changes to workflow.
   Format: {"flow_id": "...", "patch": {"ops": [...]}, "validate": true}

   Supported ops:
   - add_node: {"op": "add_node", "component_type": "ChatInput", "position": {"x": 100, "y": 100}}
   - add_note: {"op": "add_note", "content": "Note text", "position": {...}, "background_color": "amber"}
   - update_note: {"op": "update_note", "note_id": "...", "content": "...", "background_color": "..."}
   - set_node_template_value: {"op": "set_node_template_value", "node_id": "...", "field": "...", "value": ...}
  - add_edge: {"op": "add_edge", "edge": {"source": "...", "target": "...",
                                         "sourceHandle": "...", "targetHandle": "..."}}
   - remove_edge: {"op": "remove_edge", "edge_id": "..."}
   - remove_node: {"op": "remove_node", "node_id": "..."}

6. lf_node_handles - Get input/output handles for nodes.
   Returns outputs (sourceHandle names + types) and inputs (targetHandle names + input_types).
   ALWAYS call BEFORE add_edge to verify type compatibility.

7. lf_get_node_code - Get source code of a specific node.
   Use for debugging or understanding existing custom components.

8. lf_get_field_options - Get available options for a dropdown field.
   Use for dynamic fields like 'model_name' where options depend on provider/API key.
   Example: {"flow_id": "...", "node_id": "Agent-xxx", "field_name": "model_name", "refresh": true}
   Returns: options array, current_value, external_options if any.

9. lf_add_custom_component - Add custom Python component (LAST RESORT!)
   Only use when no standard component exists. See CUSTOM COMPONENTS section below.

10. lf_documentation - ACCESS LANGFLOW DOCUMENTATION
    Use this to learn about Langflow concepts, components, data types, and best practices.
    Actions:
    - 'index': List all documentation categories and pages
    - 'search': Search by query (e.g., "custom component", "data types", "deployment")
    - 'read': Get full content of a specific page by slug or filename
    ALWAYS use this when you need detailed information about Langflow features!

═══════════════════════════════════════════════════════════════════════════════
LANGFLOW KNOWLEDGE BASE
═══════════════════════════════════════════════════════════════════════════════

Langflow is an open-source, Python-based framework for building AI applications.
Key concepts you should know:

FLOWS: Functional representations of application workflows
- Consist of components connected by edges (data ports)
- Test in Playground before deploying

COMPONENTS: Building blocks of flows
- Each performs a specific task (LLM, data processing, etc.)
- Have inputs, outputs, and configurable parameters
- Port colors indicate data types

DATA TYPES (port colors):
- Message (Indigo): Chat messages with text, sender, session
- Data (Red): Structured key-value pairs
- DataFrame (Pink): Tabular data
- LanguageModel (Fuchsia): LLM instances
- Tool (Cyan): Agent functions
- Embeddings (Emerald): Vector embeddings

For detailed information, use lf_documentation tool!

═══════════════════════════════════════════════════════════════════════════════
STANDARD WORKFLOW
═══════════════════════════════════════════════════════════════════════════════

1. Get current state: lf_workflow_get
2. Find suitable component: lf_list_components → lf_get_component_info
3. Add nodes: lf_workflow_patch with add_node ops
4. Verify handles: lf_node_handles for source and target nodes
5. Connect nodes: lf_workflow_patch with add_edge ops
6. Configure fields: lf_workflow_patch with set_node_template_value ops
7. VERIFY RESULT: lf_check_workflow to ensure everything is correct!

═══════════════════════════════════════════════════════════════════════════════
COMMON WORKFLOW PATTERNS
═══════════════════════════════════════════════════════════════════════════════

PATTERN 1: Simple Chat Agent with QueryRouter (RECOMMENDED)
Components: ChatInput → QueryRouterModel → Agent → ChatOutput
Steps:
  1. add_node ChatInput at x=200, y=400
2. add_node QueryRouterModel at x=400, y=200
3. add_node Agent at x=600, y=400
4. add_node ChatOutput at x=1000, y=400
5. Configure Agent: set_node_template_value field="agent_llm" value="connect_other_models"
6. add_edge: QueryRouterModel.model_output → Agent.agent_llm
7. add_edge: ChatInput.message → Agent.input_value
8. add_edge: Agent.response → ChatOutput.input_value
Note: QueryRouterModel uses QUERYROUTER_API_KEY from global variables

PATTERN 1B: Simple Chat Agent (Built-in LLM)
Components: ChatInput → Agent → ChatOutput
Use if user wants Agent's built-in LLM (requires separate API key config)

PATTERN 2: RAG with QueryRouter
Components: ChatInput → Retriever → Prompt Template → QueryRouterModel → ChatOutput
Key: Connect vector store to retriever, use QueryRouter for LLM inference

PATTERN 3: Document Processing
Components: FileLoader → TextSplitter → Embeddings → VectorStore
Key: Use correct text splitter for document type

PATTERN 4: API Integration
Components: Webhook/TextInput → ProcessingComponents → APIRequest/Output
Key: Use existing API components before creating custom ones

═══════════════════════════════════════════════════════════════════════════════
WORKING WITH DROPDOWN FIELDS
═══════════════════════════════════════════════════════════════════════════════

STATIC DROPDOWNS (options known upfront):
1. Options visible in lf_workflow_get and lf_get_component_info
2. Set value: {"op": "set_node_template_value", "node_id": "...", "field": "...", "value": "option_from_list"}

Example - Setting Agent's Model Provider:
1. Call lf_get_component_info for "Agent" or check lf_workflow_get
2. Find agent_llm field with options: ["QueryRouter", "OpenAI", "Anthropic", ...]
3. Set: {"op": "set_node_template_value", "node_id": "...", "field": "agent_llm", "value": "QueryRouter"}

DYNAMIC DROPDOWNS (options loaded from external API):
- Field: "model_name" - list of models depends on provider and API key
- Options are NOT visible until API key is set
- Use lf_get_field_options to fetch current options:
  {"flow_id": "...", "node_id": "Agent-xxx", "field_name": "model_name", "refresh": true}
- This triggers the provider's API to fetch available models

Workflow for setting dynamic model:
1. Set provider: agent_llm = "QueryRouter" (or other provider)
2. Set API key: {"op": "set_node_template_value", "node_id": "...", "field": "api_key", "value": "sk-..."}
3. Get models: lf_get_field_options for "model_name" with refresh=true
   → Returns: {"options": ["gpt-4o", "gpt-4o-mini", "claude-3-sonnet", ...]}
4. Set model: {"op": "set_node_template_value", "node_id": "...", "field": "model_name", "value": "gpt-4o-mini"}

Note: If api_key is empty or invalid, options will be empty. For QueryRouter, the API key
should be stored as global variable QUERYROUTER_API_KEY.

Special dropdown values:
- "connect_other_models" - enables external LLM connection to agent_llm input
- This value appears in external_options, not the main options list

After setting a dropdown with real_time_refresh=True:
- Template updates automatically (new fields may appear/disappear)
- Call lf_node_handles again to get updated input_types

═══════════════════════════════════════════════════════════════════════════════
EDGE CONNECTIONS - TYPE VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

BEFORE every add_edge:
1. Call lf_node_handles for BOTH source and target nodes
2. Check source output "types" matches target input "input_types"
3. If input_types is EMPTY [] - configure node first!

COMMON ISSUE: Dynamic input_types
Some inputs are empty by default. Example:
- Agent's "agent_llm" starts with input_types=[]
- FIRST set: {"op": "set_node_template_value", "node_id": "Agent-xxx",
             "field": "agent_llm", "value": "connect_other_models"}
- THEN connect the LLM component

Common handle names (verify with lf_node_handles):
- ChatInput → message (Message)
- Agent → input_value (Message), agent_llm (LanguageModel after config)
- Agent outputs → response (Message)
- QueryRouterModel → model_output (LanguageModel) ← PREFERRED!
- OpenAIModel → model_output (LanguageModel)
- ChatOutput ← input_value (Message)

═══════════════════════════════════════════════════════════════════════════════
CUSTOM COMPONENTS (ONLY IF STANDARD COMPONENTS ARE INSUFFICIENT)
═══════════════════════════════════════════════════════════════════════════════

Basic structure:
```python
from langflow.custom import Component
from langflow.io import MessageTextInput, StrInput, DropdownInput, Output
from langflow.schema import Data, Message

class MyComponent(Component):
    display_name = "My Component"
    description = "What it does"
    icon = "code"

    inputs = [
        MessageTextInput(name="text", display_name="Text", info="Description"),
        DropdownInput(name="option", display_name="Option", options=["a", "b"], value="a"),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process"),
    ]

    def process(self) -> Message:
        result = self.text.upper() if self.option == "a" else self.text.lower()
        return Message(text=result)
```

Available input types:
- StrInput, MultilineInput, MessageTextInput (text inputs)
- IntInput, FloatInput, BoolInput (primitives)
- DropdownInput (with options=[...])
- SecretStrInput (API keys)
- DataInput, HandleInput (typed connections)

Return types:
- Message(text="...") for text/chat
- Data(data={...}) for structured data

═══════════════════════════════════════════════════════════════════════════════
COMMON COMPONENTS REFERENCE
═══════════════════════════════════════════════════════════════════════════════

INPUT/OUTPUT:
- ChatInput: User message input for chat interfaces (outputs Message)
- ChatOutput: Display chat responses (accepts Message)
- TextInput/TextOutput: Simple text handling
- FileLoader: Load files (PDF, CSV, JSON, etc.)
- Webhook: Receive HTTP requests

MODELS (LLM Providers):
★ QueryRouterModel (QueryRouter) - PREFERRED! Unified access to 100+ models
  - Component type: "QueryRouterModel"
  - Uses QUERYROUTER_API_KEY from global variables
  - Provides OpenAI, Anthropic, Google, DeepSeek, and many other models
  - Single API key for all providers
  - Output: model_output (LanguageModel)

Alternative providers (use only if user explicitly requests):
- OpenAIModel, AnthropicModel, GoogleGenerativeAIModel, GroqModel, OllamaModel
- Each outputs LanguageModel type for Agent connections

PROCESSING:
- Prompt Template: Format text with variables (use {variable_name} syntax)
- CombineText: Concatenate multiple texts
- SplitText: Split text into chunks
- ParseData: Extract fields from Data objects
- ConditionalRouter: Branch based on conditions

AGENTS:
- Agent: AI agent with tools and memory support
  - WITH QueryRouter (RECOMMENDED):
    1. Add QueryRouterModel node
    2. Set Agent's agent_llm="connect_other_models"
    3. Connect QueryRouterModel.model_output → Agent.agent_llm
  - Built-in LLM: Just set api_key field directly on Agent

MEMORY:
- Memory: Store/retrieve conversation history
- ChatMemory: Specialized for chat contexts

VECTOR STORES:
- Chroma, Pinecone, Qdrant, Weaviate, FAISS, etc.
- Each needs Embeddings input

═══════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

"invalid handles" ERROR:
1. Call lf_node_handles for both nodes
2. Check types compatibility
3. If input_types is [], configure the node first

Disconnected nodes warning:
1. Call lf_check_workflow to find all issues
2. Connect nodes or remove unused ones

Missing required fields:
1. Use lf_check_workflow to find missing fields
2. Set values with set_node_template_value

DO NOT repeat failed operations without fixing the root cause!
ALWAYS verify with lf_check_workflow after making changes!"""


@router.post("/chat", response_model=FlowAssistantChatResponse, status_code=200)
async def flow_assistant_chat(
    request: FlowAssistantChatRequest,
    current_user: CurrentActiveUser,
):
    import json

    api_key = await _get_queryrouter_api_key_for_user(user_id=current_user.id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QUERYROUTER_API_KEY not found. Set it as a Global Variable named QUERYROUTER_API_KEY.",
        )

    model = request.model or os.getenv("LANGFLOW_FLOW_ASSISTANT_MODEL", "")
    if not model:
        raise HTTPException(status_code=400, detail="Model is required. Pick a model from /flow-assistant/models.")
    client = AsyncOpenAI(api_key=api_key, base_url=QUERYROUTER_BASE_URL)

    tools = _build_openai_tools()
    messages = _build_openai_messages(flow_id=request.flow_id, message=request.message, history=request.history)

    tool_calls_log: list[ToolCallDetail] = []
    is_reasoning = _is_reasoning_model(model)
    max_iterations = _get_max_iterations()
    iteration = 0

    try:
        while True:
            iteration += 1
            if max_iterations > 0 and iteration > max_iterations:
                break

            try:
                extra_body: dict[str, Any] = {}
                if is_reasoning:
                    extra_body["include_reasoning"] = True

                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                    extra_body=extra_body if extra_body else None,
                )
            except Exception as exc:
                await logger.aerror(f"Flow assistant LLM error: {exc!s}")
                raise HTTPException(status_code=500, detail="LLM request failed") from exc

            msg = resp.choices[0].message
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else {}
            reasoning_details = msg_dict.get("reasoning_details")

            if msg.tool_calls:
                tool_calls_payload: list[dict[str, Any]] = []
                for tc in msg.tool_calls:
                    tc_dump = tc.model_dump() if hasattr(tc, "model_dump") else {}
                    tool_calls_payload.append(tc_dump)
                _ensure_tool_call_ids(tool_calls_payload)

                assistant_message: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls_payload,
                }
                if reasoning_details:
                    assistant_message["reasoning_details"] = reasoning_details
                messages.append(assistant_message)

                for idx, tc in enumerate(msg.tool_calls):
                    fn = tc.function
                    tool_name = fn.name
                    tool_args_raw = fn.arguments or "{}"
                    try:
                        tool_args = json.loads(tool_args_raw)
                    except Exception:  # noqa: BLE001
                        tool_args = {}
                    tool_args = _maybe_inject_flow_id(tool_name=tool_name, tool_args=tool_args, flow_id=request.flow_id)

                    tool_error: str | None = None
                    tool_result_text: str | None = None

                    try:
                        tool_result = await call_workflow_tool(
                            tool_name=tool_name,
                            arguments=tool_args,
                            user_id=current_user.id,
                        )
                        tool_result_text = "\n".join([c.text for c in tool_result if getattr(c, "text", None)])
                    except WorkflowEditError as exc:
                        tool_error = str(exc)
                        tool_result_text = f"ERROR: {exc}"
                    except Exception as exc:  # noqa: BLE001
                        tool_error = str(exc)
                        tool_result_text = f"ERROR: {exc}"

                    tool_calls_log.append(
                        ToolCallDetail(
                            name=tool_name,
                            arguments=tool_args,
                            result=tool_result_text if not tool_error else None,
                            error=tool_error,
                        )
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_calls_payload[idx]["id"],
                            "content": tool_result_text,
                        }
                    )
                continue

            final_text = msg.content or ""
            return FlowAssistantChatResponse(
                message=final_text,
                tool_calls=tool_calls_log,
            )
    finally:
        await client.close()

    raise HTTPException(
        status_code=500,
        detail=f"Assistant reached max iterations ({max_iterations}). "
        "Set LANGFLOW_FLOW_ASSISTANT_MAX_ITERATIONS=0 for unlimited.",
    )


def _sse_event(event_type: str, data: Any) -> str:
    """Format an SSE event."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _is_reasoning_model(model: str) -> bool:
    """Check if model requires reasoning token preservation (Gemini, etc.)."""
    model_lower = model.lower()
    return any(provider in model_lower for provider in ["gemini", "google", "deepseek-r1", "o1", "o3"])


async def _stream_assistant_chat(
    *,
    flow_id: UUID,
    message: str,
    history: list[AssistantMessage],
    model: str,
    user_id: UUID,
    api_key: str,
) -> AsyncGenerator[str, None]:
    """Stream assistant chat responses with tool calls."""
    client = AsyncOpenAI(api_key=api_key, base_url=QUERYROUTER_BASE_URL)
    tools = _build_openai_tools()

    messages = _build_openai_messages(flow_id=flow_id, message=message, history=history)

    is_reasoning = _is_reasoning_model(model)
    max_iterations = _get_max_iterations()
    iteration = 0

    try:
        while True:
            iteration += 1
            if max_iterations > 0 and iteration > max_iterations:
                break

            try:
                extra_body: dict[str, Any] = {}
                if is_reasoning:
                    extra_body["include_reasoning"] = True

                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                    stream=True,
                    extra_body=extra_body if extra_body else None,
                )
            except Exception as exc:  # noqa: BLE001
                await logger.aerror(f"Flow assistant LLM stream error: {exc!s}")
                yield _sse_event("error", {"message": "LLM request failed", "detail": str(exc)})
                return

            content_buffer = ""
            reasoning_details: list[Any] = []
            reasoning_content_buffer = ""
            tool_calls_buffer: dict[int, dict[str, Any]] = {}
            final_message: dict[str, Any] | None = None

            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                choice_dict = choice.model_dump() if hasattr(choice, "model_dump") else {}

                if choice_dict.get("message"):
                    final_message = choice_dict["message"]
                    if final_message.get("content"):
                        yield _sse_event("text", {"content": final_message["content"]})
                    continue

                delta = choice.delta
                delta_dict = delta.model_dump() if hasattr(delta, "model_dump") else {}

                if delta_dict.get("reasoning_details"):
                    for detail in delta_dict["reasoning_details"]:
                        reasoning_details.append(detail)
                        if isinstance(detail, dict) and "content" in detail:
                            reasoning_content_buffer += detail.get("content", "")
                        elif isinstance(detail, str):
                            reasoning_content_buffer += detail

                        if reasoning_content_buffer:
                            yield _sse_event(
                                "reasoning",
                                {
                                    "content": detail.get("content", "") if isinstance(detail, dict) else str(detail),
                                    "summary": detail.get("summary") if isinstance(detail, dict) else None,
                                },
                            )

                if delta.content:
                    content_buffer += delta.content
                    yield _sse_event("text", {"content": delta.content})

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        tc_dict = tc.model_dump() if hasattr(tc, "model_dump") else {}

                        if idx not in tool_calls_buffer:
                            tool_call_id = tc.id or _new_tool_call_id()
                            tool_calls_buffer[idx] = {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }

                        if tc.id:
                            tool_calls_buffer[idx]["id"] = tc.id
                        if tc_dict.get("type"):
                            tool_calls_buffer[idx]["type"] = tc_dict["type"]

                        if tc.function:
                            if tc.function.name:
                                tool_calls_buffer[idx]["function"]["name"] = tc.function.name
                                yield _sse_event("tool_start", {"name": tc.function.name})
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments

                        for key, val in tc_dict.items():
                            if key not in ("index", "id", "type", "function") and val is not None:
                                tool_calls_buffer[idx][key] = val

            if final_message:
                if not final_message.get("tool_calls"):
                    yield _sse_event("done", {"message": final_message.get("content", content_buffer)})
                    return
                tool_calls_for_execution = final_message["tool_calls"]
                _ensure_tool_call_ids(tool_calls_for_execution)
                tool_calls_for_execution = _filter_complete_tool_calls(tool_calls_for_execution)
                if not tool_calls_for_execution:
                    yield _sse_event("done", {"message": final_message.get("content", content_buffer)})
                    return
                assistant_message = {
                    "role": "assistant",
                    "content": final_message.get("content") or content_buffer,
                    "tool_calls": tool_calls_for_execution,
                }
                if final_message.get("reasoning_details"):
                    assistant_message["reasoning_details"] = final_message["reasoning_details"]
            else:
                if not tool_calls_buffer:
                    yield _sse_event("done", {"message": content_buffer})
                    return
                tool_calls_for_execution = list(tool_calls_buffer.values())
                _ensure_tool_call_ids(tool_calls_for_execution)
                tool_calls_for_execution = _filter_complete_tool_calls(tool_calls_for_execution)
                if not tool_calls_for_execution:
                    yield _sse_event("done", {"message": content_buffer})
                    return
                assistant_message = {
                    "role": "assistant",
                    "content": content_buffer,
                    "tool_calls": tool_calls_for_execution,
                }
                if reasoning_details:
                    assistant_message["reasoning_details"] = reasoning_details

            messages.append(assistant_message)

            for tc in tool_calls_for_execution:
                tc_func = tc.get("function", {})
                tool_name = tc_func.get("name", "")
                tool_args_raw = tc_func.get("arguments", "")
                try:
                    tool_args = json.loads(tool_args_raw) if tool_args_raw else {}
                except Exception:  # noqa: BLE001
                    tool_args = {}
                tool_args = _maybe_inject_flow_id(tool_name=tool_name, tool_args=tool_args, flow_id=flow_id)

                yield _sse_event("tool_call", {"name": tool_name, "arguments": tool_args})

                tool_error: str | None = None
                tool_result_text: str | None = None

                try:
                    tool_result = await call_workflow_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        user_id=user_id,
                    )
                    tool_result_text = "\n".join([c.text for c in tool_result if getattr(c, "text", None)])
                except WorkflowEditError as exc:
                    tool_error = str(exc)
                    tool_result_text = f"ERROR: {exc}"
                except Exception as exc:  # noqa: BLE001
                    tool_error = str(exc)
                    tool_result_text = f"ERROR: {exc}"

                yield _sse_event(
                    "tool_result",
                    {"name": tool_name, "result": tool_result_text, "error": tool_error},
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result_text,
                    }
                )

            await asyncio.sleep(0.01)
    finally:
        await client.close()

    yield _sse_event(
        "error",
        {
            "message": f"Assistant reached max iterations ({max_iterations}). "
            "Set LANGFLOW_FLOW_ASSISTANT_MAX_ITERATIONS=0 for unlimited."
        },
    )


@router.post("/chat/stream")
async def flow_assistant_chat_stream(
    request: FlowAssistantChatRequest,
    current_user: CurrentActiveUser,
):
    """Stream assistant chat responses using Server-Sent Events."""
    api_key = await _get_queryrouter_api_key_for_user(user_id=current_user.id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QUERYROUTER_API_KEY not found. Set it as a Global Variable named QUERYROUTER_API_KEY.",
        )

    model = request.model or os.getenv("LANGFLOW_FLOW_ASSISTANT_MODEL", "")
    if not model:
        raise HTTPException(status_code=400, detail="Model is required. Pick a model from /flow-assistant/models.")

    return StreamingResponse(
        _stream_assistant_chat(
            flow_id=request.flow_id,
            message=request.message,
            history=request.history,
            model=model,
            user_id=current_user.id,
            api_key=api_key,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
