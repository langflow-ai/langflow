from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware
from pydantic import ValidationError

from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import (
    adapt_graph_events_to_executor_shape,
)
from lfx.components.models_and_agents.agent_helpers.messages_input_builder import (
    build_initial_messages,
)
from lfx.components.models_and_agents.memory import MemoryComponent

if TYPE_CHECKING:
    from langchain_core.tools import Tool

    from lfx.schema.log import SendMessageFunctionType

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.utils import get_chat_output_sender_name
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
from lfx.helpers.base_model import build_model_from_schema
from lfx.inputs.inputs import BoolInput, DropdownInput, ModelInput, StrInput
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, TableInput
from lfx.log.logger import logger
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.table import EditMode
from lfx.utils.constants import MESSAGE_SENDER_AI


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


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
                "Supports dynamic placeholders: {current_date}, {model_name}."
            ),
            value=(
                "You are a helpful assistant that can use tools to answer questions and perform tasks. "
                "Today is {current_date}. You are powered by {model_name}."
            ),
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
            self.tools.append(current_date_tool)

        # Add calculator tool if enabled (zero-config arithmetic)
        if getattr(self, "add_calculator_tool", False):
            if not isinstance(self.tools, list):  # type: ignore[has-type]
                self.tools = []
            calculator_tool = (await CalculatorComponent(**self.get_base_args()).to_toolkit()).pop(0)

            if not isinstance(calculator_tool, StructuredTool):
                msg = "CalculatorComponent must be converted to a StructuredTool"
                raise TypeError(msg)
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
        """Replace {current_date} / {model_name} placeholders in the system prompt.

        Uses str.replace (not str.format) so user prompts containing literal braces
        such as JSON examples ({"key": 1}) never break the agent.
        """
        if not prompt:
            return prompt
        replacements = {
            "{current_date}": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "{model_name}": self._get_resolved_model_name(),
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
        """
        middleware = self._build_middleware()
        return create_agent(
            model=self._get_llm(),
            tools=self.tools or [],
            system_prompt=self.system_prompt or "",
            middleware=middleware or None,
        )

    def _build_middleware(self) -> list:
        middleware: list = []
        max_iterations = getattr(self, "max_iterations", None)
        if max_iterations:
            middleware.append(ModelCallLimitMiddleware(run_limit=int(max_iterations)))
        if getattr(self, "handle_parsing_errors", False):
            middleware.append(ToolRetryMiddleware(max_retries=2))
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

        stream = adapt_graph_events_to_executor_shape(
            agent.astream_events(
                input_dict,
                config={"callbacks": [AgentAsyncHandler(self.log), *self._get_shared_callbacks()]},
                version="v2",
            )
        )
        result = await process_agent_events(
            stream,
            agent_message,
            cast("SendMessageFunctionType", self.send_message),
        )

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

    def _preprocess_schema(self, schema):
        """Preprocess schema to ensure correct data types for build_model_from_schema."""
        processed_schema = []
        for field in schema:
            processed_field = {
                "name": str(field.get("name", "field")),
                "type": str(field.get("type", "str")),
                "description": str(field.get("description", "")),
                "multiple": field.get("multiple", False),
            }
            # Ensure multiple is handled correctly
            if isinstance(processed_field["multiple"], str):
                processed_field["multiple"] = processed_field["multiple"].lower() in [
                    "true",
                    "1",
                    "t",
                    "y",
                    "yes",
                ]
            processed_schema.append(processed_field)
        return processed_schema

    async def build_structured_output_base(self, content: str):
        """Build structured output with optional BaseModel validation."""
        json_pattern = r"\{.*\}"
        schema_error_msg = "Try setting an output schema"

        # Try to parse content as JSON first
        json_data = None
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(json_pattern, content, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return {"content": content, "error": schema_error_msg}
            else:
                return {"content": content, "error": schema_error_msg}

        # If no output schema provided, return parsed JSON without validation
        if not hasattr(self, "output_schema") or not self.output_schema or len(self.output_schema) == 0:
            return json_data

        # Use BaseModel validation with schema
        try:
            processed_schema = self._preprocess_schema(self.output_schema)
            output_model = build_model_from_schema(processed_schema)

            # Validate against the schema
            if isinstance(json_data, list):
                # Multiple objects
                validated_objects = []
                for item in json_data:
                    try:
                        validated_obj = output_model.model_validate(item)
                        validated_objects.append(validated_obj.model_dump())
                    except ValidationError as e:
                        await logger.aerror(f"Validation error for item: {e}")
                        # Include invalid items with error info
                        validated_objects.append({"data": item, "validation_error": str(e)})
                return validated_objects

            # Single object
            try:
                validated_obj = output_model.model_validate(json_data)
                return [validated_obj.model_dump()]  # Return as list for consistency
            except ValidationError as e:
                await logger.aerror(f"Validation error: {e}")
                return [{"data": json_data, "validation_error": str(e)}]

        except (TypeError, ValueError) as e:
            await logger.aerror(f"Error building structured output: {e}")
            # Fallback to parsed JSON without validation
            return json_data

    async def json_response(self) -> Data:
        """Convert agent response to structured JSON Data output with schema validation."""
        # Always use structured chat agent for JSON response mode for better JSON formatting
        try:
            system_components = []

            # 1. Agent Instructions (system_prompt).
            # Inject dynamic placeholders HERE so user-authored format_instructions
            # and schema descriptions appended later keep their literal {...} tokens.
            agent_instructions = self._inject_dynamic_prompt_values(getattr(self, "system_prompt", "") or "") or ""
            if agent_instructions:
                system_components.append(f"{agent_instructions}")

            # 2. Format Instructions
            format_instructions = getattr(self, "format_instructions", "") or ""
            if format_instructions:
                system_components.append(f"Format instructions: {format_instructions}")

            # 3. Schema Information from BaseModel
            if hasattr(self, "output_schema") and self.output_schema and len(self.output_schema) > 0:
                try:
                    processed_schema = self._preprocess_schema(self.output_schema)
                    output_model = build_model_from_schema(processed_schema)
                    schema_dict = output_model.model_json_schema()
                    schema_info = (
                        "You are given some text that may include format instructions, "
                        "explanations, or other content alongside a JSON schema.\n\n"
                        "Your task:\n"
                        "- Extract only the JSON schema.\n"
                        "- Return it as valid JSON.\n"
                        "- Do not include format instructions, explanations, or extra text.\n\n"
                        "Input:\n"
                        f"{json.dumps(schema_dict, indent=2)}\n\n"
                        "Output (only JSON schema):"
                    )
                    system_components.append(schema_info)
                except (ValidationError, ValueError, TypeError, KeyError) as e:
                    await logger.aerror(f"Could not build schema for prompt: {e}", exc_info=True)

            # Combine all components. Injection already applied on agent_instructions
            # above; do NOT re-run it here so literal {...} tokens in format
            # instructions / schema descriptions stay intact.
            combined_instructions = "\n\n".join(system_components) if system_components else ""
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=combined_instructions,
            )

            # Create and run structured chat agent
            try:
                structured_agent = self.create_agent_runnable()
            except (NotImplementedError, ValueError, TypeError) as e:
                await logger.aerror(f"Error with structured chat agent: {e}")
                raise
            try:
                result = await self.run_agent(structured_agent)
            except (
                ExceptionWithMessageError,
                ValueError,
                TypeError,
                RuntimeError,
            ) as e:
                await logger.aerror(f"Error with structured agent result: {e}")
                raise
            # Extract content from structured agent result
            if hasattr(result, "content"):
                content = result.content
            elif hasattr(result, "text"):
                content = result.text
            else:
                content = str(result)

        except (
            ExceptionWithMessageError,
            ValueError,
            TypeError,
            NotImplementedError,
            AttributeError,
        ) as e:
            await logger.aerror(f"Error with structured chat agent: {e}")
            # Fallback to regular agent
            content_str = "No content returned from agent"
            return Data(data={"content": content_str, "error": str(e)})

        # Process with structured output validation
        try:
            structured_output = await self.build_structured_output_base(content)

            # Handle different output formats
            if isinstance(structured_output, list) and structured_output:
                if len(structured_output) == 1:
                    return Data(data=structured_output[0])
                return Data(data={"results": structured_output})
            if isinstance(structured_output, dict):
                return Data(data=structured_output)
            return Data(data={"content": content})

        except (ValueError, TypeError) as e:
            await logger.aerror(f"Error in structured output processing: {e}")
            return Data(data={"content": content, "error": str(e)})

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
