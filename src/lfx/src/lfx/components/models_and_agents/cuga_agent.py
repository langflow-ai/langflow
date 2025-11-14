import asyncio
import json
import re
import traceback
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langflow.field_typing import Tool
from langflow.io import BoolInput, DropdownInput, IntInput, MultilineInput, Output, TableInput

# from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message
from langflow.schema.table import EditMode
from pydantic import ValidationError

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.events import ExceptionWithMessageError
from lfx.base.models.model_input_constants import (
    ALL_PROVIDER_FIELDS,
    MODEL_DYNAMIC_UPDATE_FIELDS,
    MODEL_PROVIDERS,
    MODEL_PROVIDERS_DICT,
    MODELS_METADATA,
)
from lfx.base.models.model_utils import get_model_name
from lfx.components.helpers import CurrentDateComponent
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.custom.custom_component.component import _get_component_toolkit
from lfx.custom.utils import update_component_build_config
from lfx.helpers.base_model import build_model_from_schema
from lfx.log.logger import logger

if TYPE_CHECKING:
    from langflow.schema.log import SendMessageFunctionType


def set_advanced_true(component_input):
    """Set the advanced flag to True for a component input.

    Args:
        component_input: The component input to modify

    Returns:
        The modified component input with advanced=True
    """
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["OpenAI"]


class CugaComponent(ToolCallingAgentComponent):
    """Cuga Agent Component for advanced AI task execution.

    The Cuga component is an advanced AI agent that can execute complex tasks using
    various tools, browser automation, and structured output generation. It supports
    custom policies, web applications, and API interactions.

    Attributes:
        display_name: Human-readable name for the component
        description: Brief description of the component's purpose
        documentation: URL to component documentation
        icon: Icon identifier for the UI
        name: Internal component name
    """

    display_name: str = "Cuga"
    description: str = "Define the Cuga agent's policies, then assign it a task."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    name = "Cuga"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    # Filter out json_mode from OpenAI inputs since we handle structured output differently
    openai_inputs_filtered = [
        input_field
        for input_field in MODEL_PROVIDERS_DICT["OpenAI"]["inputs"]
        if not (hasattr(input_field, "name") and input_field.name == "json_mode")
    ]

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            info="The provider of the language model that the agent will use to generate responses.",
            options=[*MODEL_PROVIDERS_LIST, "Custom"],
            value="OpenAI",
            real_time_refresh=True,
            input_types=[],
            options_metadata=[MODELS_METADATA[key] for key in MODEL_PROVIDERS_LIST] + [{"icon": "brain"}],
        ),
        *openai_inputs_filtered,
        MultilineInput(
            name="policies",
            display_name="Policies",
            info=(
                "Custom instructions or policies for the agent to adhere to during its operation.\n"
                "Example:\n"
                "## Plan\n"
                "< planning instructions e.g. which tools and when to use>\n"
                "## Answer\n"
                "< final answer instructions how to answer>"
            ),
            value="",
            advanced=False,
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
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
        BoolInput(
            name="lite_mode",
            display_name="Enable CugaLite",
            info="Enable CugaLite for simple API tasks (faster execution).",
            value=True,
            advanced=False,
        ),
        IntInput(
            name="lite_mode_tool_threshold",
            display_name="CugaLite Tool Threshold",
            info="Route to CugaLite if app has fewer than this many tools.",
            value=25,
            advanced=False,
        ),
        BoolInput(
            name="browser_enabled",
            display_name="Enable Browser",
            info="Toggle to enable a built-in browser tool for web scraping and searching.",
            value=False,
            advanced=False,
        ),
        MultilineInput(
            name="web_apps",
            display_name="Web applications",
            info=(
                "Define a list of web applications that cuga will open when enable browser is true. "
                "Currently only supports one web application. Example: https://example.com"
            ),
            value="",
            advanced=False,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
        Output(name="structured_response", display_name="Structured Response", method="json_response", tool_mode=False),
    ]

    async def call_agent(
        self, current_input: str, tools: list[Tool], history_messages: list[Message], llm
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the Cuga agent with the given input and tools.

        This method initializes and runs the Cuga agent, processing the input through
        the agent's workflow and yielding events for real-time monitoring.

        Args:
            current_input: The user input to process
            tools: List of available tools for the agent
            history_messages: Previous conversation history
            llm: The language model instance to use

        Yields:
            dict: Agent events including tool usage, thinking, and final results

        Raises:
            ValueError: If there's an error in agent initialization
            TypeError: If there's a type error in processing
            RuntimeError: If there's a runtime error during execution
            ConnectionError: If there's a connection issue
        """
        yield {
            "event": "on_chain_start",
            "run_id": str(uuid.uuid4()),
            "name": "CUGA_initializing",
            "data": {"input": {"input": current_input, "chat_history": []}},
        }
        logger.debug(f"LLM MODEL TYPE: {type(llm)}")
        if current_input:
            # Import settings first
            from cuga.config import settings

            # Use Dynaconf's set() method to update settings dynamically
            # This properly updates the settings object without corruption
            logger.debug("Updating CUGA settings via Dynaconf set() method")

            settings.advanced_features.registry = False
            settings.advanced_features.lite_mode = self.lite_mode
            settings.advanced_features.lite_mode_tool_threshold = self.lite_mode_tool_threshold

            if self.browser_enabled:
                logger.debug("browser_enabled is true, setting mode to hybrid")
                settings.advanced_features.mode = "hybrid"
                settings.advanced_features.use_vision = False
            else:
                logger.debug("browser_enabled is false, setting mode to api")
                settings.advanced_features.mode = "api"

            from cuga.backend.activity_tracker.tracker import ActivityTracker
            from cuga.backend.cuga_graph.nodes.api.variables_manager.manager import VariablesManager
            from cuga.backend.cuga_graph.utils.agent_loop import StreamEvent
            from cuga.backend.cuga_graph.utils.controller import (
                AgentRunner as CugaAgent,
            )
            from cuga.backend.cuga_graph.utils.controller import (
                ExperimentResult as AgentResult,
            )
            from cuga.backend.llm.models import LLMManager
            from cuga.configurations.instructions_manager import InstructionsManager

            var_manager = VariablesManager()

            # Reset var_manager if this is the first message in history
            logger.debug(f"[CUGA] Checking history_messages: count={len(history_messages) if history_messages else 0}")
            if not history_messages or len(history_messages) == 0:
                logger.debug("[CUGA] First message in history detected, resetting var_manager")
                var_manager.reset()
            else:
                logger.debug(f"[CUGA] Continuing conversation with {len(history_messages)} previous messages")

            llm_manager = LLMManager()
            llm_manager.set_llm(llm)
            instructions_manager = InstructionsManager()
            logger.debug(f"policies are: {self.policies}")
            instructions_manager.set_instructions_from_one_file(self.policies)
            tracker = ActivityTracker()
            tracker.set_tools(tools)
            cuga_agent = CugaAgent(browser_enabled=self.browser_enabled)
            if self.browser_enabled:
                await cuga_agent.initialize_freemode_env(start_url=self.web_apps.strip(), interface_mode="browser_only")
            else:
                await cuga_agent.initialize_appworld_env()

            yield {
                "event": "on_chain_start",
                "run_id": str(uuid.uuid4()),
                "name": "CUGA_thinking...",
                "data": {"input": {"input": current_input, "chat_history": []}},
            }
            logger.debug(f"[CUGA] current web apps are {self.web_apps}")
            logger.debug(f"[CUGA] Processing input: {current_input}")
            try:
                # Convert history to LangChain format for the event
                lc_messages = []
                for msg in history_messages:
                    if hasattr(msg, "sender") and msg.sender == "Human":
                        lc_messages.append(HumanMessage(content=msg.text))
                    else:
                        lc_messages.append(AIMessage(content=msg.text))

                await asyncio.sleep(0.5)

                # 2. Build final response
                response_parts = []

                response_parts.append(f"Processed input: '{current_input}'")
                response_parts.append(f"Available tools: {len(tools)}")
                last_event: StreamEvent | None = None
                tool_run_id: str | None = None
                # 3. Chain end event with AgentFinish
                async for event in cuga_agent.run_task_generic_yield(eval_mode=False, goal=current_input):
                    logger.debug(f"recieved event {event}")
                    if last_event is not None and tool_run_id is not None:
                        logger.debug(f"last event {last_event}")
                        try:
                            # TODO: Extract data
                            data_dict = json.loads(last_event.data)
                        except json.JSONDecodeError:
                            data_dict = last_event.data
                        if last_event.name == "CodeAgent":
                            data_dict = data_dict["code"]
                        yield {
                            "event": "on_tool_end",
                            "run_id": tool_run_id,
                            "name": last_event.name,
                            "data": {"output": data_dict},
                        }
                    if isinstance(event, StreamEvent):
                        tool_run_id = str(uuid.uuid4())
                        last_event = StreamEvent(name=event.name, data=event.data)
                        tool_event = {
                            "event": "on_tool_start",
                            "run_id": tool_run_id,
                            "name": event.name,
                            "data": {"input": {}},
                        }
                        logger.debug(f"[CUGA] Yielding tool_start event: {event.name}")
                        yield tool_event

                    if isinstance(event, AgentResult):
                        task_result = event
                        end_event = {
                            "event": "on_chain_end",
                            "run_id": str(uuid.uuid4()),
                            "name": "CugaAgent",
                            "data": {"output": AgentFinish(return_values={"output": task_result.answer}, log="")},
                        }
                        answer_preview = task_result.answer[:100] if task_result.answer else "None"
                        logger.info(f"[CUGA] Yielding chain_end event with answer: {answer_preview}...")
                        yield end_event

            except (ValueError, TypeError, RuntimeError, ConnectionError) as e:
                logger.error(f"An error occurred: {e!s}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = f"CUGA Agent error: {e!s}"
                logger.error(f"[CUGA] Error occurred: {error_msg}")

                # Emit error event
                yield {
                    "event": "on_chain_error",
                    "run_id": str(uuid.uuid4()),
                    "name": "CugaAgent",
                    "data": {"error": error_msg},
                }

    async def message_response(self) -> Message:
        """Generate a message response using the Cuga agent.

        This method processes the input through the Cuga agent and returns a structured
        message response. It handles agent initialization, tool setup, and event processing.

        Returns:
            Message: The agent's response message

        Raises:
            Exception: If there's an error during agent execution
        """
        logger.debug("[CUGA] Starting Cuga agent run for message_response.")
        logger.debug(f"[CUGA] Agent input value: {self.input_value}")

        # Validate input is not empty
        if not self.input_value or not str(self.input_value).strip():
            msg = "Message cannot be empty. Please provide a valid message."
            raise ValueError(msg)

        try:
            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()

            # Create agent message for event processing
            from lfx.schema.content_block import ContentBlock
            from lfx.schema.message import MESSAGE_SENDER_AI

            agent_message = Message(
                sender=MESSAGE_SENDER_AI,
                sender_name="Cuga",
                properties={"icon": "Bot", "state": "partial"},
                content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
                session_id=self.graph.session_id,
            )

            # Get input text
            input_text = self.input_value.text if hasattr(self.input_value, "text") else str(self.input_value)

            # Create event iterator from call_agent
            event_iterator = self.call_agent(
                current_input=input_text, tools=self.tools or [], history_messages=self.chat_history, llm=llm_model
            )

            # Process events using the existing event processing system
            from lfx.base.agents.events import process_agent_events

            # Create a wrapper that forces DB updates for event handlers
            # This ensures the UI can see loading steps in real-time via polling
            async def force_db_update_send_message(message, id_=None, *, skip_db_update=False):  # noqa: ARG001
                # Always persist to DB so polling-based UI shows loading steps in real-time
                content_blocks_len = len(message.content_blocks[0].contents) if message.content_blocks else 0
                logger.debug(
                    f"[CUGA] Sending message update - state: {message.properties.state}, "
                    f"content_blocks: {content_blocks_len}"
                )
                result = await self.send_message(message, id_=id_, skip_db_update=False)
                logger.debug(f"[CUGA] Message saved to DB with ID: {result.id if result else 'None'}")
                return result

            result = await process_agent_events(
                event_iterator, agent_message, cast("SendMessageFunctionType", force_db_update_send_message)
            )

            logger.info("[CUGA] Agent run finished successfully.")
            logger.info(f"[CUGA] Agent output: {result}")

            # Store result for potential JSON output
            self._agent_result = result

        except Exception as e:
            logger.error(f"[CUGA] Error in message_response: {e}")
            logger.error(f"An error occurred: {e!s}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Check if error is related to Playwright installation
            error_str = str(e).lower()
            if "playwright install" in error_str:
                msg = (
                    "Playwright is not installed. Please install Playwright Chromium using: "
                    "uv run -m playwright install chromium"
                )
                raise ValueError(msg) from e

            raise
        else:
            return result

    async def get_agent_requirements(self):
        """Get the agent requirements for the Cuga agent.

        This method retrieves and configures all necessary components for the agent
        including the language model, chat history, and tools.

        Returns:
            tuple: A tuple containing (llm_model, chat_history, tools)

        Raises:
            ValueError: If no language model is selected or if there's an error
                in model initialization
        """
        llm_model, display_name = await self.get_llm()
        if llm_model is None:
            msg = "No language model selected. Please choose a model to proceed."
            raise ValueError(msg)
        self.model_name = get_model_name(llm_model, display_name=display_name)

        # Get memory data
        self.chat_history = await self.get_memory_data()
        if isinstance(self.chat_history, Message):
            self.chat_history = [self.chat_history]

        # Add current date tool if enabled
        if self.add_current_date_tool:
            if not isinstance(self.tools, list):
                self.tools = []
            current_date_tool = (await CurrentDateComponent(**self.get_base_args()).to_toolkit()).pop(0)
            if not isinstance(current_date_tool, StructuredTool):
                msg = "CurrentDateComponent must be converted to a StructuredTool"
                raise TypeError(msg)
            self.tools.append(current_date_tool)

        # --- ADDED LOGGING START ---
        logger.debug("[CUGA] Retrieved agent requirements: LLM, chat history, and tools.")
        logger.debug(f"[CUGA] LLM model: {self.model_name}")
        logger.debug(f"[CUGA] Number of chat history messages: {len(self.chat_history)}")
        logger.debug(f"[CUGA] Tools available: {[tool.name for tool in self.tools]}")
        logger.debug(f"[CUGA] metadata: {[tool.metadata for tool in self.tools]}")
        # --- ADDED LOGGING END ---

        return llm_model, self.chat_history, self.tools

    def _preprocess_schema(self, schema):
        """Preprocess schema to ensure correct data types for build_model_from_schema.

        This method validates and normalizes the output schema to ensure it's compatible
        with the Pydantic model building process.

        Args:
            schema: List of schema field definitions

        Returns:
            list: Processed schema with validated data types
        """
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
                processed_field["multiple"] = processed_field["multiple"].lower() in ["true", "1", "t", "y", "yes"]
            processed_schema.append(processed_field)
        return processed_schema

    async def build_structured_output_base(self, content: str):
        """Build structured output with optional BaseModel validation.

        This method parses JSON content from the agent response and optionally validates
        it against a provided schema using Pydantic models.

        Args:
            content: The raw content from the agent response

        Returns:
            dict or list: Parsed and optionally validated JSON data
        """
        # --- ADDED LOGGING START ---
        logger.debug(f"[CUGA] Attempting to build structured output from content: {content}")
        # --- ADDED LOGGING END ---

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
                    logger.warning("[CUGA] Could not parse content as JSON even with regex match.")
                    return {"content": content, "error": schema_error_msg}
            else:
                logger.warning("[CUGA] No JSON pattern found in the content.")
                return {"content": content, "error": schema_error_msg}

        # If no output schema provided, return parsed JSON without validation
        if not hasattr(self, "output_schema") or not self.output_schema or len(self.output_schema) == 0:
            logger.debug("[CUGA] No output schema provided. Returning parsed JSON without validation.")
            return json_data

        # Use BaseModel validation with schema
        try:
            logger.debug("[CUGA] Output schema detected. Validating structured output against schema.")
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
                        await logger.aerror(f"[CUGA] Validation error for item: {e}")
                        validated_objects.append({"data": item, "validation_error": str(e)})
                return validated_objects

            # Single object
            try:
                validated_obj = output_model.model_validate(json_data)
                return [validated_obj.model_dump()]
            except ValidationError as e:
                await logger.aerror(f"[CUGA] Validation error: {e}")
                return [{"data": json_data, "validation_error": str(e)}]

        except (TypeError, ValueError) as e:
            await logger.aerror(f"[CUGA] Error building structured output: {e}")
            return json_data

    async def json_response(self) -> Data:
        """Convert agent response to structured JSON Data output with schema validation.

        This method generates a structured JSON response by combining system instructions,
        format instructions, and schema information, then processing the agent's response
        through structured output validation.

        Returns:
            Data: Structured data object containing the validated JSON response

        Raises:
            ExceptionWithMessageError: If there's an error in structured processing
            ValueError: If there's a validation error
            TypeError: If there's a type error in processing
        """
        # --- ADDED LOGGING START ---
        logger.debug("[CUGA] Starting Cuga agent run for json_response.")
        logger.debug(f"[CUGA] Agent input value: {self.input_value}")
        # --- ADDED LOGGING END ---

        try:
            system_components = []

            # 1. Agent Instructions
            agent_instructions = getattr(self, "instructions", "") or ""
            if agent_instructions:
                system_components.append(f"{agent_instructions}")

            # 3. Format Instructions
            format_instructions = getattr(self, "format_instructions", "") or ""
            if format_instructions:
                system_components.append(f"Format instructions: {format_instructions}")

            # 4. Schema Information
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
                    await logger.aerror(f"[CUGA] Could not build schema for prompt: {e}", exc_info=True)

            # Combine all components
            combined_instructions = "\n\n".join(system_components) if system_components else ""

            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()

            # Use call_agent for structured response
            input_text = self.input_value.text if hasattr(self.input_value, "text") else str(self.input_value)

            # Modify the input to include structured output requirements
            structured_input = (
                f"{combined_instructions}\n\nUser Input: {input_text}\n\nPlease provide a structured JSON response."
            )

            logger.debug(f"[CUGA] Combined system prompt for structured agent: {combined_instructions}")

            content = await self.call_agent(
                current_input=structured_input,
                tools=self.tools or [],
                history_messages=self.chat_history,
                llm=llm_model,
            )

            logger.debug(f"[CUGA] Structured agent result: {content}")

        except (ExceptionWithMessageError, ValueError, TypeError, NotImplementedError, AttributeError) as e:
            await logger.aerror(f"[CUGA] Error with structured agent: {e}")
            content_str = "No content returned from Cuga agent"
            return Data(data={"content": content_str, "error": str(e)})

        # Process with structured output validation
        try:
            structured_output = await self.build_structured_output_base(content)

            # Handle different output formats
            if isinstance(structured_output, list) and structured_output:
                if len(structured_output) == 1:
                    logger.debug("[CUGA] Structured output is a single object in a list.")
                    logger.debug(f"[CUGA] Final structured output: {structured_output[0]}")
                    return Data(data=structured_output[0])
                logger.debug("[CUGA] Structured output is a list of multiple objects.")
                logger.debug(f"[CUGA] Final structured output: {structured_output}")
                return Data(data={"results": structured_output})
            if isinstance(structured_output, dict):
                logger.debug("[CUGA] Structured output is a single dictionary.")
                logger.debug(f"[CUGA] Final structured output: {structured_output}")
                return Data(data=structured_output)
            logger.debug("[CUGA] Structured output is not a list or dictionary. Returning raw content.")
            logger.debug(f"[CUGA] Final output content: {content}")
            return Data(data={"content": content})

        except (ValueError, TypeError) as e:
            await logger.aerror(f"[CUGA] Error in structured output processing: {e}")
            return Data(data={"content": content, "error": str(e)})

    async def get_memory_data(self):
        """Retrieve chat history messages.

        This method fetches the conversation history from memory, excluding the current
        input message to avoid duplication.

        Returns:
            list: List of Message objects representing the chat history
        """
        logger.debug("[CUGA] Retrieving chat history messages.")
        logger.debug(f"[CUGA] Session ID: {self.graph.session_id}")
        messages = (
            await MemoryComponent(**self.get_base_args())
            .set(session_id=self.graph.session_id, order="Ascending", n_messages=self.n_messages)
            .retrieve_messages()
        )
        logger.debug(f"[CUGA] Retrieved {len(messages)} messages from memory")
        return [
            message for message in messages if getattr(message, "id", None) != getattr(self.input_value, "id", None)
        ]

    async def get_llm(self):
        """Get language model for the Cuga agent.

        This method initializes and configures the language model based on the
        selected provider and parameters.

        Returns:
            tuple: A tuple containing (llm_model, display_name)

        Raises:
            ValueError: If the model provider is invalid or model initialization fails
        """
        logger.debug("[CUGA] Getting language model for the agent.")
        logger.debug(f"[CUGA] Requested LLM provider: {self.agent_llm}")

        if not isinstance(self.agent_llm, str):
            logger.debug("[CUGA] Agent LLM is already a model instance.")
            return self.agent_llm, None

        try:
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if not provider_info:
                msg = f"Invalid model provider: {self.agent_llm}"
                raise ValueError(msg)

            component_class = provider_info.get("component_class")
            display_name = component_class.display_name
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix", "")
            logger.debug(f"[CUGA] Successfully built LLM model from provider: {self.agent_llm}")
            return self._build_llm_model(component_class, inputs, prefix), display_name

        except (AttributeError, ValueError, TypeError, RuntimeError) as e:
            await logger.aerror(f"[CUGA] Error building {self.agent_llm} language model: {e!s}")
            msg = f"Failed to initialize language model: {e!s}"
            raise ValueError(msg) from e

    def _build_llm_model(self, component, inputs, prefix=""):
        """Build LLM model with parameters.

        This method constructs a language model instance using the provided component
        class and input parameters.

        Args:
            component: The LLM component class to instantiate
            inputs: List of input field definitions
            prefix: Optional prefix for parameter names

        Returns:
            The configured LLM model instance
        """
        model_kwargs = {}
        for input_ in inputs:
            if hasattr(self, f"{prefix}{input_.name}"):
                model_kwargs[input_.name] = getattr(self, f"{prefix}{input_.name}")
        return component.set(**model_kwargs).build_model()

    def set_component_params(self, component):
        """Set component parameters based on provider.

        This method configures component parameters according to the selected
        model provider's requirements.

        Args:
            component: The component to configure

        Returns:
            The configured component
        """
        provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
        if provider_info:
            inputs = provider_info.get("inputs")
            prefix = provider_info.get("prefix")
            model_kwargs = {}
            for input_ in inputs:
                if hasattr(self, f"{prefix}{input_.name}"):
                    model_kwargs[input_.name] = getattr(self, f"{prefix}{input_.name}")
            return component.set(**model_kwargs)
        return component

    def delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        """Delete specified fields from build_config.

        This method removes unwanted fields from the build configuration.

        Args:
            build_config: The build configuration dictionary
            fields: Fields to remove (can be dict or list of strings)
        """
        for field in fields:
            build_config.pop(field, None)

    def update_input_types(self, build_config: dotdict) -> dotdict:
        """Update input types for all fields in build_config.

        This method ensures all fields in the build configuration have proper
        input types defined.

        Args:
            build_config: The build configuration to update

        Returns:
            dotdict: Updated build configuration with input types
        """
        for key, value in build_config.items():
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        """Update build configuration based on field changes.

        This method dynamically updates the component's build configuration when
        certain fields change, particularly the model provider selection.

        Args:
            build_config: The current build configuration
            field_value: The new value for the field
            field_name: The name of the field being changed

        Returns:
            dotdict: Updated build configuration

        Raises:
            ValueError: If required keys are missing from the configuration
        """
        if field_name in ("agent_llm",):
            build_config["agent_llm"]["value"] = field_value
            provider_info = MODEL_PROVIDERS_DICT.get(field_value)
            if provider_info:
                component_class = provider_info.get("component_class")
                if component_class and hasattr(component_class, "update_build_config"):
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, "model_name"
                    )

            provider_configs: dict[str, tuple[dict, list[dict]]] = {
                provider: (
                    MODEL_PROVIDERS_DICT[provider]["fields"],
                    [
                        MODEL_PROVIDERS_DICT[other_provider]["fields"]
                        for other_provider in MODEL_PROVIDERS_DICT
                        if other_provider != provider
                    ],
                )
                for provider in MODEL_PROVIDERS_DICT
            }
            if field_value in provider_configs:
                fields_to_add, fields_to_delete = provider_configs[field_value]

                # Delete fields from other providers
                for fields in fields_to_delete:
                    self.delete_fields(build_config, fields)

                # Add provider-specific fields
                if field_value == "OpenAI" and not any(field in build_config for field in fields_to_add):
                    build_config.update(fields_to_add)
                else:
                    build_config.update(fields_to_add)
                build_config["agent_llm"]["input_types"] = []
            elif field_value == "Custom":
                # Delete all provider fields
                self.delete_fields(build_config, ALL_PROVIDER_FIELDS)
                # Update with custom component
                custom_component = DropdownInput(
                    name="agent_llm",
                    display_name="Language Model",
                    options=[*sorted(MODEL_PROVIDERS), "Custom"],
                    value="Custom",
                    real_time_refresh=True,
                    input_types=["LanguageModel"],
                    options_metadata=[MODELS_METADATA[key] for key in sorted(MODELS_METADATA.keys())]
                    + [{"icon": "brain"}],
                )
                build_config.update({"agent_llm": custom_component.to_dict()})

            # Update input types for all fields
            build_config = self.update_input_types(build_config)

            # Validate required keys
            default_keys = [
                "code",
                "_type",
                "agent_llm",
                "tools",
                "input_value",
                "add_current_date_tool",
                "policies",
                "agent_description",
                "max_iterations",
                "handle_parsing_errors",
                "verbose",
            ]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)

        if (
            isinstance(self.agent_llm, str)
            and self.agent_llm in MODEL_PROVIDERS_DICT
            and field_name in MODEL_DYNAMIC_UPDATE_FIELDS
        ):
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if provider_info:
                component_class = provider_info.get("component_class")
                component_class = self.set_component_params(component_class)
                prefix = provider_info.get("prefix")
                if component_class and hasattr(component_class, "update_build_config"):
                    if isinstance(field_name, str) and isinstance(prefix, str):
                        field_name = field_name.replace(prefix, "")
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, "model_name"
                    )
        return dotdict({k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in build_config.items()})

    async def _get_tools(self) -> list[Tool]:
        """Build agent tools.

        This method constructs the list of tools available to the Cuga agent,
        including component tools and any additional configured tools.

        Returns:
            list[Tool]: List of available tools for the agent
        """
        logger.debug("[CUGA] Building agent tools.")
        component_toolkit = _get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        description = f"{agent_description}{tools_names}"
        tools = component_toolkit(component=self).get_tools(
            tool_name="Call_CugaAgent", tool_description=description, callbacks=self.get_langchain_callbacks()
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)
        logger.debug(f"[CUGA] Tools built: {[tool.name for tool in tools]}")
        return tools
