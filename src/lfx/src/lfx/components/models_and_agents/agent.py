from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.components.models_and_agents.memory import MemoryComponent

if TYPE_CHECKING:
    from langchain_core.tools import Tool

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE
from lfx.base.agents.events import ExceptionWithMessageError
from lfx.base.constants import STREAM_INFO_TEXT
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    handle_model_input_update,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.components.agentics.helpers.model_config import validate_model_selection
from lfx.components.helpers import CalculatorComponent, CurrentDateComponent
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.custom.custom_component.component import get_component_toolkit
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, ModelInput, StrInput
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, TableInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.table import EditMode


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


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
        *LCToolsAgentComponent.get_base_inputs(),
        # removed memory inputs from agent component
        # *memory_inputs,
        BoolInput(
            name="stream",
            display_name="Stream",
            info=STREAM_INFO_TEXT,
            value=False,
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
        """Override parent to include max_tokens from the Agent's input field."""
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=getattr(self, "api_key", None),
            stream=bool(getattr(self, "stream", False)),
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

    def _inject_dynamic_prompt_values(self, prompt: str | None) -> str | None:
        """Replace known env placeholders in the system prompt.

        Handles {current_date}, {model_name}, and {optional_user_context} (the
        last one ships with the structured DEFAULT_SYSTEM_PROMPT_TEMPLATE and
        is currently unused at the AgentComponent layer, so it resolves to "").
        Uses str.replace (not str.format) so user prompts containing literal
        braces such as JSON examples ({"key": 1}) never break the agent.
        """
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
        # TODO: This is a temporary fix to avoid message duplication. We should develop a function for this.
        messages = (
            await MemoryComponent(**self.get_base_args())
            .set(
                session_id=self.graph.session_id,
                context_id=self.context_id,
                order="Ascending",
                n_messages=self.n_messages,
            )
            .retrieve_messages()
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
        # Update model options with caching (for all field changes)
        # Agents require tool calling, so filter for only tool-calling capable models
        build_config = handle_model_input_update(
            component=self,
            build_config=dict(build_config),
            field_value=field_value,
            field_name=field_name,
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=lambda user_id=None: get_language_model_options(user_id=user_id, tool_calling=True),
        )
        build_config = dotdict(build_config)

        if field_name == "model":
            build_config = self.update_input_types(build_config)

            # Validate required keys
            default_keys = [
                "code",
                "_type",
                "model",
                "tools",
                "input_value",
                "add_current_date_tool",
                "add_calculator_tool",
                "system_prompt",
                "agent_description",
                "max_iterations",
                "handle_parsing_errors",
                "verbose",
            ]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
        return dotdict({k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in build_config.items()})

    async def _get_tools(self) -> list[Tool]:
        component_toolkit = get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        # TODO: Agent Description Depreciated Feature to be removed
        description = f"{agent_description}{tools_names}"

        tools = component_toolkit(component=self).get_tools(
            tool_name="Call_Agent",
            tool_description=description,
            # here we do not use the shared callbacks as we are exposing the agent as a tool
            callbacks=self.get_langchain_callbacks(),
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)

        return tools
