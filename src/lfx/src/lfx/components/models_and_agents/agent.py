from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from lfx.components.models_and_agents.memory import MemoryComponent

if TYPE_CHECKING:
    from langchain_core.tools import Tool

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.events import ExceptionWithMessageError
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.components.helpers import CurrentDateComponent
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.custom.custom_component.component import get_component_toolkit
from lfx.helpers.base_model import build_model_from_schema
from lfx.inputs.inputs import BoolInput, ModelInput
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, TableInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.table import EditMode


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
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
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
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    async def get_agent_requirements(self):
        """Get the agent requirements for the agent."""
        from langchain_core.tools import StructuredTool

        llm_model = get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=self.api_key,
        )
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

        # Set shared callbacks for tracing the tools used by the agent
        self.set_tools_callbacks(self.tools, self._get_shared_callbacks())

        return llm_model, self.chat_history, self.tools

    async def message_response(self) -> Message:
        try:
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()
            # Set up and run agent
            self.set(
                llm=llm_model,
                tools=self.tools or [],
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self.system_prompt,
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

            # 1. Agent Instructions (system_prompt)
            agent_instructions = getattr(self, "system_prompt", "") or ""
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

            # Combine all components
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
        def get_tool_calling_model_options(user_id=None):
            return get_language_model_options(user_id=user_id, tool_calling=True)

        build_config = update_model_options_in_build_config(
            component=self,
            build_config=dict(build_config),
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=get_tool_calling_model_options,
            field_name=field_name,
            field_value=field_value,
        )
        build_config = dotdict(build_config)

        # Iterate over all providers in the MODEL_PROVIDERS_DICT
        if field_name == "model":
            # Update input types for all fields
            build_config = self.update_input_types(build_config)

            # Validate required keys
            default_keys = [
                "code",
                "_type",
                "model",
                "tools",
                "input_value",
                "add_current_date_tool",
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
