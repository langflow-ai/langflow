from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware

from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import (
    adapt_graph_events_to_executor_shape,
)
from lfx.components.models_and_agents.agent_helpers.messages_input_builder import (
    build_initial_messages,
)
from lfx.components.models_and_agents.agent_helpers.placeholder_corrective_middleware import (
    WatsonXPlaceholderMiddleware,
)
from lfx.components.models_and_agents.agent_helpers.single_tool_call_middleware import (
    SingleToolCallMiddleware,
)
from lfx.components.models_and_agents.memory import MemoryComponent, aget_agent_chat_history

if TYPE_CHECKING:
    from langchain_core.tools import Tool

    from lfx.schema.log import OnTokenFunctionType, SendMessageFunctionType

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.token_callback import TokenUsageCallbackHandler
from lfx.base.agents.utils import get_chat_output_sender_name
from lfx.base.constants import STREAM_INFO_TEXT
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    handle_model_input_update,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.components.agentics.helpers.model_config import validate_model_selection
from lfx.components.helpers import CalculatorComponent, CurrentDateComponent
from lfx.components.langchain_utilities.ibm_granite_handler import is_watsonx_model
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.custom.custom_component.component import get_component_toolkit
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, ModelInput, StrInput
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, TableInput
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.table import EditMode
from lfx.utils.constants import MESSAGE_SENDER_AI


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


def _agent_base_inputs():
    """Return base inputs tailored to AgentComponent's create_agent path.

    `get_base_inputs()` returns a shared list — replace, don't mutate. We drop
    inputs that are no-ops here and override info text on the inputs whose
    semantics shifted under create_agent.

    `verbose` is dropped because the create_agent event stream already surfaces
    every agent step via the "Agent Steps" content blocks; the legacy boolean
    has nothing to toggle. Saved flows that still carry a `verbose` value just
    ignore it on load (the schema no longer declares it).
    """
    drop = {"verbose"}
    overrides = {
        "handle_parsing_errors": BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
            info=(
                "Adds tool-execution retry as a safety net. `create_agent` already "
                "feeds tool-call validation errors back to the LLM automatically; "
                "this flag layers `ToolRetryMiddleware` on top so transient tool "
                "runtime failures are retried (max 2 retries)."
            ),
        ),
        "max_iterations": IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=15,
            advanced=True,
            range_spec=RangeSpec(min=1, max=128000, step=1, step_type="int"),
            info=(
                "Maximum number of model calls the agent can make before stopping "
                "(maps to `ModelCallLimitMiddleware.run_limit` on the create_agent "
                "path). Must be at least 1 — it is a safety cap, never 'unlimited'."
            ),
        ),
    }
    return [overrides.get(inp.name, inp) for inp in LCToolsAgentComponent.get_base_inputs() if inp.name not in drop]


def _extract_text_content(value) -> str:
    """Pull a string payload from a Message-like, AIMessage-like, or string value."""
    if isinstance(value, str):
        return value
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return str(value) if value is not None else ""


@contextmanager
def _suppress_send_message(component: Any):
    """Temporarily replace component.send_message with a no-op for the duration of the block.

    Used during the structured-output prompt fallback: run_agent streams the agent's
    final answer through self.send_message (correct for message_response), but in
    json_response the orchestrator parses that text into structured Data which the
    downstream Chat Output emits — leaving the original emission in place produces a
    duplicate message in the playground. The original method is always restored on exit,
    even when the wrapped call raises.
    """
    original = component.send_message

    async def _noop(message, *_args, **_kwargs):
        return message

    component.send_message = _noop
    try:
        yield
    finally:
        component.send_message = original


class AgentComponent(ToolCallingAgentComponent):
    display_name: str = "Agent"
    description: str = "Define the agent's instructions, then enter a task to complete using tools."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    beta = False
    name = "Agent"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
            # Agents require tool calling — the filter is honored by
            # ``handle_model_input_update`` so models that can't run with
            # tools never reach the picker (and any saved selection that
            # no longer satisfies the constraint is auto-replaced).
            filters={"tool_calling": True},
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
            real_time_refresh=True,
            advanced=True,
        ),
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            combobox=True,
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
            info="The project ID associated with the foundation model (IBM watsonx.ai only)",
            show=False,
            required=False,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info=(
                "System Prompt: Initial instructions and context provided to guide the agent's behavior. "
                "Supports dynamic placeholders: {current_date}, {model_name}, {optional_user_context}."
            ),
            value=DEFAULT_SYSTEM_PROMPT_TEMPLATE,
            advanced=False,
        ),
        MessageTextInput(
            name="context_id",
            display_name="Context ID",
            info="The context ID of the chat. Adds an extra layer to the local memory.",
            value="",
            advanced=True,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Chat History Messages",
            value=100,
            info="Number of chat history messages to retrieve.",
            advanced=True,
            show=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate. Field name varies by provider.",
            advanced=True,
            range_spec=RangeSpec(min=1, max=128000, step=1, step_type="int"),
        ),
        MultilineInput(
            name="format_instructions",
            display_name="Output Format Instructions",
            info="Generic Template for structured output formatting. Valid only with Structured response.",
            value=(
                "You are an AI that extracts structured JSON objects from unstructured text. "
                "Use a predefined schema with expected types (str, int, float, bool, dict). "
                "Extract ALL relevant instances that match the schema - if multiple patterns exist, capture them all. "
                "Fill missing or ambiguous values with defaults: null for missing values. "
                "Remove exact duplicates but keep variations that have different field values. "
                "Always return valid JSON in the expected format, never throw errors. "
                "If multiple objects can be extracted, return them all in the structured format."
            ),
            advanced=True,
        ),
        TableInput(
            name="output_schema",
            display_name="Output Schema",
            info=(
                "Schema Validation: Define the structure and data types for structured output. "
                "No validation if no output schema."
            ),
            advanced=True,
            required=False,
            value=[],
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "description of field",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate the data type of the output field (e.g., str, int, float, bool, dict)."),
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                },
                {
                    "name": "multiple",
                    "display_name": "As List",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
            ],
        ),
        *_agent_base_inputs(),
        # removed memory inputs from agent component
        # *memory_inputs,
        BoolInput(
            name="stream",
            display_name="Stream",
            info=STREAM_INFO_TEXT,
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
        BoolInput(
            name="add_calculator_tool",
            display_name="Calculator",
            advanced=True,
            info=(
                "If true, adds a zero-config arithmetic calculator tool to the agent "
                "(safe: only +, -, *, /, ** operators via AST)."
            ),
            value=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
        Output(
            name="structured_response",
            display_name="Structured Response",
            method="json_response",
            types=["Data"],
        ),
    ]

    def _resolve_selected_model(self):
        """Resolve the selected model, including legacy agent_llm/model_name inputs."""
        try:
            from langchain_core.language_models import BaseLanguageModel

            if isinstance(self.model, BaseLanguageModel):
                return self.model
        except ImportError:
            pass

        if isinstance(self.model, list) and self.model:
            return self.model

        legacy_provider = getattr(self, "agent_llm", None)
        legacy_model_name = getattr(self, "model_name", None)
        if not legacy_provider or not legacy_model_name:
            return self.model

        options = get_language_model_options(user_id=self.user_id)
        for option in options:
            if option.get("provider") == legacy_provider and option.get("name") == legacy_model_name:
                return [option]

        return [
            {
                "name": legacy_model_name,
                "provider": legacy_provider,
                "metadata": {},
            }
        ]

    def _get_max_tokens_value(self):
        """Return the user-supplied max_tokens or None when unset/zero."""
        val = getattr(self, "max_tokens", None)
        if val in {"", 0}:
            return None
        return val

    def _get_llm(self):
        """Override parent to include max_tokens from the Agent's input field.

        Streaming is mandatory for AgentComponent: ``runnable.astream_events(v2)`` only
        emits ``on_chat_model_stream`` chunks when the underlying chat model is
        instantiated with ``streaming=True``. Unlike the LanguageModel component (where
        ``stream`` is a user-facing toggle), the Agent has no opt-out — the toggle is
        kept in the UI for backwards compatibility but is intentionally ignored here.
        Without ``stream=True``, the chat model accumulates the whole response and
        only emits ``on_chat_model_end``, silently disabling the Playground's live-
        typing view and breaking the streaming contract on the /events surface.
        """
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=getattr(self, "api_key", None),
            stream=True,
            max_tokens=self._get_max_tokens_value(),
            watsonx_url=getattr(self, "base_url_ibm_watsonx", None),
            watsonx_project_id=getattr(self, "project_id", None),
        )

    async def get_agent_requirements(self):
        """Get the agent requirements for the agent."""
        from langchain_core.tools import StructuredTool

        selected_model = self._resolve_selected_model()
        try:
            from langchain_core.language_models import BaseLanguageModel

            is_connected_model = isinstance(selected_model, BaseLanguageModel)
        except ImportError:
            is_connected_model = False

        if not is_connected_model:
            validate_model_selection(selected_model)

        # Ensure _get_llm() uses the resolved model (e.g. from legacy agent_llm/model_name)
        self.model = selected_model
        llm_model = self._get_llm()
        if llm_model is None:
            msg = "No language model selected. Please choose a model to proceed."
            raise ValueError(msg)

        # Get memory data
        self.chat_history = await self.get_memory_data()
        await logger.adebug(f"Retrieved {len(self.chat_history)} chat history messages")
        if isinstance(self.chat_history, Message):
            self.chat_history = [self.chat_history]

        # Add current date tool if enabled
        if self.add_current_date_tool:
            if not isinstance(self.tools, list):  # type: ignore[has-type]
                self.tools = []
            current_date_tool = (await CurrentDateComponent(**self.get_base_args()).to_toolkit()).pop(0)

            if not isinstance(current_date_tool, StructuredTool):
                msg = "CurrentDateComponent must be converted to a StructuredTool"
                raise TypeError(msg)
            # Skip if an externally-connected tool already provides the same name.
            # Duplicate tool names are rejected by Anthropic/Gemini with HTTP 400.
            if not any(getattr(t, "name", None) == current_date_tool.name for t in self.tools):
                self.tools.append(current_date_tool)

        # Add calculator tool if enabled (zero-config arithmetic)
        if getattr(self, "add_calculator_tool", False):
            if not isinstance(self.tools, list):  # type: ignore[has-type]
                self.tools = []
            calculator_tool = (await CalculatorComponent(**self.get_base_args()).to_toolkit()).pop(0)

            if not isinstance(calculator_tool, StructuredTool):
                msg = "CalculatorComponent must be converted to a StructuredTool"
                raise TypeError(msg)
            # Skip if an externally-connected tool already provides the same name.
            # Duplicate tool names are rejected by Anthropic/Gemini with HTTP 400.
            if not any(getattr(t, "name", None) == calculator_tool.name for t in self.tools):
                self.tools.append(calculator_tool)

        # Set shared callbacks for tracing the tools used by the agent
        self.set_tools_callbacks(self.tools, self._get_shared_callbacks())

        return llm_model, self.chat_history, self.tools

    def _get_resolved_model_name(self) -> str:
        """Best-effort human-readable model name for {model_name} injection."""
        try:
            from langchain_core.language_models import BaseLanguageModel

            if isinstance(self.model, BaseLanguageModel):
                return type(self.model).__name__
        except ImportError:
            pass

        if isinstance(self.model, list) and self.model:
            first = self.model[0]
            if isinstance(first, dict):
                name = first.get("name")
                if isinstance(name, str) and name:
                    return name

        legacy_model_name = getattr(self, "model_name", None)
        if isinstance(legacy_model_name, str) and legacy_model_name:
            return legacy_model_name
        return ""

    def _inject_dynamic_prompt_values(self, prompt: Any | None) -> str | None:
        """Replace known env placeholders in the system prompt.

        Handles {current_date}, {model_name}, and {optional_user_context} (the
        last one ships with the structured DEFAULT_SYSTEM_PROMPT_TEMPLATE and
        is currently unused at the AgentComponent layer, so it resolves to "").
        Uses str.replace (not str.format) so user prompts containing literal
        braces such as JSON examples ({"key": 1}) never break the agent.

        `system_prompt` is a connectable MultilineInput, so the value can arrive
        as a Message (e.g. a Prompt node wired in). Normalize it to text first —
        a raw Message has no `.replace` and used to crash the agent build.
        """
        if prompt is None:
            return None
        prompt = _extract_text_content(prompt)
        if not prompt:
            return prompt
        replacements = {
            "{current_date}": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "{model_name}": self._get_resolved_model_name(),
            "{optional_user_context}": "",
        }
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def create_agent_runnable(self):
        """Build the LangGraph `CompiledStateGraph` via `langchain.agents.create_agent`.

        Replaces the legacy `AgentExecutor` runnable inherited from
        `ToolCallingAgentComponent`. Other agent components (tool_calling, csv, json,
        openapi, sql*, vector_store_router) keep the legacy path — only AgentComponent
        runs on the new graph API.

        `max_iterations` and `handle_parsing_errors` (legacy AgentExecutor knobs) are
        translated to LangGraph middleware. Without that translation those user inputs
        would silently become no-ops on the new API.

        Provider notes:
        - WatsonX/Granite work natively with create_agent — `ChatWatsonx.bind_tools`
          handles tool_choice correctly. The legacy `create_granite_agent` path was
          dropped because it hardcoded `tool_choice='required'`, which the WatsonX
          API now rejects.
        - Ollama and other small/local models often emit malformed tool args. The
          ToolRetryMiddleware (default `retry_on=(Exception,)`, `on_failure='continue'`)
          catches Pydantic ValidationErrors from bad args and feeds the error back
          to the LLM as a retry signal, so the agent recovers gracefully.
        """
        llm = self._get_llm()
        tools = self.tools or []

        # Eager bind_tools validation. `create_agent(...)` is lazy — without this,
        # an LLM that doesn't support tool calling fails on the first user message
        # instead of when the user wires up the component, which is a much worse UX.
        # Gated on a non-empty tools list so a no-tool Agent on a plain chat model
        # (which legitimately has no `bind_tools`) isn't shut out at flow-build time.
        # Providers signal "no tool calling" inconsistently — `NotImplementedError`
        # (langchain default), `AttributeError` (no `bind_tools` attr), or `TypeError`
        # (signature mismatch). Treat all three as the same UX failure.
        if tools:
            try:
                llm.bind_tools(tools)
            except (NotImplementedError, AttributeError, TypeError) as exc:
                # Include the underlying error so a broken tool schema or a
                # provider implementation bug is not silently disguised as a
                # "model can't call tools" UX error.
                msg = (
                    f"{self.display_name} does not support tool calling, "
                    "or one of the connected tools failed to bind. "
                    "Please connect a tool-calling capable language model and "
                    f"verify your tools are well-formed. Underlying error: {exc!s}"
                )
                raise NotImplementedError(msg) from exc

        middleware = self._build_middleware(llm)
        return create_agent(
            model=llm,
            tools=tools,
            system_prompt=self.system_prompt or "",
            middleware=middleware or None,
        )

    def _compute_recursion_limit(self) -> int:
        """Derive the LangGraph recursion_limit from the user-set max_iterations.

        Mirrors the clamp in `_build_middleware` (max(1, max_iterations)) so a
        saved 0 or negative value cannot under-cap the graph below one full
        iteration. The +5 buffer covers start/end/router overhead.
        """
        raw = getattr(self, "max_iterations", None)
        run_limit = max(1, int(raw)) if raw is not None else 15
        return run_limit * 2 + 5

    def _build_middleware(self, llm: Any) -> list:
        # `llm` is passed in (rather than re-fetched via `self._get_llm()`)
        # because some providers do credential resolution / client instantiation
        # lazily on each call. The caller — `create_agent_runnable` — already
        # resolved it once for `bind_tools`, so reuse that instance here.
        middleware: list = []
        max_iterations = getattr(self, "max_iterations", None)
        if max_iterations is not None:
            # `max_iterations` is a safety cap, not an "unlimited" toggle. A saved
            # 0 or negative value (falsy) must NOT silently drop the limiter and
            # allow an unbounded model/tool loop — clamp it to a real minimum.
            run_limit = max(1, int(max_iterations))
            middleware.append(ModelCallLimitMiddleware(run_limit=run_limit))
        # ToolRetryMiddleware only matters when there ARE tools to retry. Attaching
        # it on a no-tools agent inflates the compiled graph and adds per-invocation
        # middleware overhead for nothing, which is a measurable contributor to
        # trivial-prompt latency (QA UI-003).
        if getattr(self, "handle_parsing_errors", False) and self.tools:
            middleware.append(ToolRetryMiddleware(max_retries=2))
        # WatsonX models have two known platform quirks; both still reproduce on
        # the current API, so we keep the protections from the legacy
        # `create_granite_agent` path.
        # 1. Multi-tool-call assistant turns are rejected ("This model only
        #    supports single tool-calls at once!"). Clamp to one per turn.
        # 2. Tool args occasionally come back as literal placeholder strings
        #    (e.g. `<result-from-search>`). Re-invoke once with a corrective
        #    SystemMessage.
        # Order: SingleToolCallMiddleware first (outermost) so the clamp is
        # applied to the final response, including any corrective re-invoke
        # produced by WatsonXPlaceholderMiddleware.
        if is_watsonx_model(llm):
            middleware.append(SingleToolCallMiddleware())
            middleware.append(WatsonXPlaceholderMiddleware())
        return middleware

    async def run_agent(self, agent) -> Message:
        """Run the LangGraph `CompiledStateGraph` and return the final agent Message.

        Overrides the legacy `LCAgentComponent.run_agent` (which builds an
        `{"input": str, "chat_history": [...]}` dict for `AgentExecutor`). The graph
        wants `{"messages": [BaseMessage, ...]}`. The event stream is wrapped with
        `adapt_graph_events_to_executor_shape` so the legacy `process_agent_events`
        (in `lfx.base.agents.events`) can be reused unchanged.
        """
        messages = build_initial_messages(
            input_value=self.input_value,
            chat_history=getattr(self, "chat_history", None),
        )
        input_dict = {"messages": messages}

        agent_message = self._build_initial_agent_message()
        token_usage_handler = TokenUsageCallbackHandler()

        # Stream tokens to the event manager when running inside the Langflow runtime.
        # This is what powers the live-typing view in the chat UI.
        on_token_callback: OnTokenFunctionType | None = None
        if getattr(self, "_event_manager", None):
            on_token_callback = cast("OnTokenFunctionType", self._event_manager.on_token)

        # Align LangGraph's `recursion_limit` with `max_iterations` so the
        # middleware cap (ModelCallLimitMiddleware) is what bounds the loop —
        # not LangGraph's default 25-step guard, which fires at ~12 model+tool
        # iterations and raises a raw GraphRecursionError (QA UI-009/UI-010).
        # Each iteration is ~2 graph steps (model node + tools node); add 5
        # for start/end overhead.
        recursion_limit = self._compute_recursion_limit()

        stream = adapt_graph_events_to_executor_shape(
            agent.astream_events(
                input_dict,
                config={
                    "callbacks": [
                        AgentAsyncHandler(self.log),
                        token_usage_handler,
                        *self._get_shared_callbacks(),
                    ],
                    "recursion_limit": recursion_limit,
                },
                version="v2",
            )
        )
        try:
            result = await process_agent_events(
                stream,
                agent_message,
                cast("SendMessageFunctionType", self.send_message),
                on_token_callback,
            )
        except ExceptionWithMessageError as e:
            # Drop the half-stored partial message from the DB (only if it was
            # actually persisted) and tell the frontend to remove the stale bubble.
            if hasattr(e, "agent_message"):
                msg_id = e.agent_message.get_id()
                if msg_id:
                    await delete_message(id_=msg_id)
                await self._send_message_event(e.agent_message, category="remove_message")
            logger.error(f"ExceptionWithMessageError: {e}")
            raise

        usage_data = token_usage_handler.get_usage()
        if usage_data:
            self._token_usage = usage_data
            result.properties.usage = usage_data
            # Only round-trip the DB when the message was stored (Chat Output wired).
            # `_should_skip_message=True` leaves `result.get_id()` empty; persisting
            # then would create a phantom row.
            if result.get_id():
                stored_result = await self._update_stored_message(result)
                await self._send_message_event(stored_result)
                result = stored_result

        self.status = result
        return result

    def _build_initial_agent_message(self) -> Message:
        """Construct the placeholder agent Message that `process_agent_events` mutates."""
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        sender_name = get_chat_output_sender_name(self) or self.display_name or "AI"
        return Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=sender_name,
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )

    async def message_response(self) -> Message:
        try:
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()
            # Set up and run agent
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self._inject_dynamic_prompt_values(self.system_prompt),
            )
            agent = self.create_agent_runnable()
            result = await self.run_agent(agent)

            # Store result for potential JSON output
            self._agent_result = result

        except (ValueError, TypeError, KeyError) as e:
            await logger.aerror(f"{type(e).__name__}: {e!s}")
            raise
        except ExceptionWithMessageError as e:
            await logger.aerror(f"ExceptionWithMessageError occurred: {e}")
            raise
        # Avoid catching blind Exception; let truly unexpected exceptions propagate
        except Exception as e:
            await logger.aerror(f"Unexpected error: {e!s}")
            raise
        else:
            return result

    async def json_response(self) -> Data:
        """Produce structured Data via native LLM structured output, with prompt-based fallback.

        Native path (no tools, llm has with_structured_output) bypasses the agent loop and
        returns provider-validated JSON. When tools are attached, falls back to running the
        agent with a schema-augmented system prompt and parsing the final message content.
        """
        from lfx.components.models_and_agents.structured_output.structured_output_orchestrator import (
            orchestrate_structured_output,
        )

        try:
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()
        except (ValueError, TypeError) as exc:
            await logger.aerror(f"json_response.requirements_failed: {exc}")
            return Data(data={"content": "", "error": str(exc)})

        injected_system_prompt = self._inject_dynamic_prompt_values(getattr(self, "system_prompt", "") or "") or ""
        format_instructions = getattr(self, "format_instructions", "") or ""
        output_schema = getattr(self, "output_schema", None) or []
        has_tools = bool(self.tools)

        async def _run_agent_for_fallback(augmented_prompt: str) -> str:
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=augmented_prompt,
            )
            agent_runnable = self.create_agent_runnable()
            with _suppress_send_message(self):
                result = await self.run_agent(agent_runnable)
            return _extract_text_content(result)

        try:
            return await orchestrate_structured_output(
                llm=llm_model,
                output_schema=output_schema,
                system_prompt=injected_system_prompt,
                format_instructions=format_instructions,
                input_value=_extract_text_content(self.input_value),
                run_prompt_fallback=_run_agent_for_fallback,
                prefer_native=not has_tools,
            )
        except (
            ExceptionWithMessageError,
            ValueError,
            TypeError,
            NotImplementedError,
            AttributeError,
        ) as exc:
            await logger.aerror(f"json_response.orchestration_failed: {exc}")
            return Data(data={"content": "", "error": str(exc)})

    async def get_memory_data(self):
        # Scope by flow_id so default playground session names (e.g. "New Session 0")
        # cannot leak chat history across unrelated flows. See issue #13059.
        # The helper also returns [] when n_messages == 0, preserving the
        # explicit "memory disabled" contract from MemoryComponent.retrieve_messages.
        messages = await aget_agent_chat_history(
            session_id=self.graph.session_id,
            flow_id=getattr(self.graph, "flow_id", None),
            context_id=self.context_id,
            n_messages=self.n_messages,
        )
        return [
            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)
        ]

    def update_input_types(self, build_config: dotdict) -> dotdict:
        """Update input types for all fields in build_config."""
        for key, value in build_config.items():
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config

    async def update_build_config(
        self,
        build_config: dotdict,
        field_value: list[dict],
        field_name: str | None = None,
    ) -> dotdict:
        # Update model options with caching (for all field changes).
        # The tool-calling constraint lives on the ModelInput's ``filters``
        # field (declared above); ``handle_model_input_update`` reads it
        # and applies the filter to both the dropdown options and the
        # sticky-default re-injection path.
        build_config = handle_model_input_update(
            component=self,
            build_config=dict(build_config),
            field_value=field_value,
            field_name=field_name,
        )
        build_config = dotdict(build_config)

        if field_name == "model":
            build_config = self.update_input_types(build_config)

            # Validate required keys. `verbose` was dropped from the input set
            # (see `_agent_base_inputs` — the create_agent event stream already
            # surfaces every step), so it is intentionally NOT required here.
            # Saved flows that still carry a `verbose` value just ignore it on
            # load.
            default_keys = [
                "code",
                "_type",
                "model",
                "tools",
                "input_value",
                "add_current_date_tool",
                "add_calculator_tool",
                "system_prompt",
                "max_iterations",
                "handle_parsing_errors",
            ]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
        return dotdict({k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in build_config.items()})

    async def _get_tools(self) -> list[Tool]:
        component_toolkit = get_component_toolkit()

        tools = component_toolkit(component=self).get_tools(
            tool_name="Call_Agent",
            # here we do not use the shared callbacks as we are exposing the agent as a tool
            callbacks=self.get_langchain_callbacks(),
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)

        return tools
