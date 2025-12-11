import asyncio
import json
import traceback
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from loguru import logger

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.models.model_utils import get_model_name
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_llm,
    update_model_options_in_build_config,
)
from lfx.components.helpers import CurrentDateComponent
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.custom.custom_component.component import _get_component_toolkit
from lfx.field_typing import Tool
from lfx.inputs.inputs import BoolInput, DropdownInput, ModelInput, SecretStrInput
from lfx.io import IntInput, MultilineInput, Output
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message

if TYPE_CHECKING:
    from lfx.schema.log import SendMessageFunctionType


def set_advanced_true(component_input):
    """Set the advanced flag to True for a component input.

    Args:
        component_input: The component input to modify

    Returns:
        The modified component input with advanced=True
    """
    component_input.advanced = True
    return component_input


class CugaComponent(ToolCallingAgentComponent):
    """Cuga Agent Component for advanced AI task execution.

    The Cuga component is an advanced AI agent that can execute complex tasks using
    various tools and browser automation. It supports custom instructions, web applications,
    and API interactions.

    Attributes:
        display_name: Human-readable name for the component
        description: Brief description of the component's purpose
        documentation: URL to component documentation
        icon: Icon identifier for the UI
        name: Internal component name
    """

    display_name: str = "Cuga"
    description: str = "Define the Cuga agent's instructions, then assign it a task."
    documentation: str = "https://docs.langflow.org/bundles-cuga"
    icon = "bot"
    name = "Cuga"

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
            name="instructions",
            display_name="Instructions",
            info=(
                "Custom instructions for the agent to adhere to during its operation.\n"
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
            info="Faster reasoning for simple tasks. Enable CugaLite for simple API tasks.",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="lite_mode_tool_threshold",
            display_name="CugaLite Tool Threshold",
            info="Route to CugaLite if app has fewer than this many tools.",
            value=25,
            advanced=True,
        ),
        DropdownInput(
            name="decomposition_strategy",
            display_name="Decomposition Strategy",
            info="Strategy for task decomposition: 'flexible' allows multiple subtasks per app,\n"
            " 'exact' enforces one subtask per app.",
            options=["flexible", "exact"],
            value="flexible",
            advanced=True,
        ),
        BoolInput(
            name="browser_enabled",
            display_name="Enable Browser",
            info="Toggle to enable a built-in browser tool for web scraping and searching.",
            value=False,
            advanced=True,
        ),
        MultilineInput(
            name="web_apps",
            display_name="Web applications",
            info=(
                "Cuga will automatically start this web application when Enable Browser is true. "
                "Currently only supports one web application. Example: https://example.com"
            ),
            value="",
            advanced=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
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
        logger.debug(f"[CUGA] LLM MODEL TYPE: {type(llm)}")
        if current_input:
            # Import settings first
            from cuga.config import settings

            # Use Dynaconf's set() method to update settings dynamically
            # This properly updates the settings object without corruption
            logger.debug("[CUGA] Updating CUGA settings via Dynaconf set() method")

            settings.advanced_features.registry = False
            settings.advanced_features.lite_mode = self.lite_mode
            settings.advanced_features.lite_mode_tool_threshold = self.lite_mode_tool_threshold
            settings.advanced_features.decomposition_strategy = self.decomposition_strategy

            if self.browser_enabled:
                logger.debug("[CUGA] browser_enabled is true, setting mode to hybrid")
                settings.advanced_features.mode = "hybrid"
                settings.advanced_features.use_vision = False
            else:
                logger.debug("[CUGA] browser_enabled is false, setting mode to api")
                settings.advanced_features.mode = "api"

            from cuga.backend.activity_tracker.tracker import ActivityTracker
            from cuga.backend.cuga_graph.utils.agent_loop import StreamEvent
            from cuga.backend.cuga_graph.utils.controller import (
                AgentRunner as CugaAgent,
            )
            from cuga.backend.cuga_graph.utils.controller import (
                ExperimentResult as AgentResult,
            )
            from cuga.backend.llm.models import LLMManager
            from cuga.configurations.instructions_manager import InstructionsManager

            # Reset var_manager if this is the first message in history
            logger.debug(f"[CUGA] Checking history_messages: count={len(history_messages) if history_messages else 0}")
            if not history_messages or len(history_messages) == 0:
                logger.debug("[CUGA] First message in history detected, resetting var_manager")
            else:
                logger.debug(f"[CUGA] Continuing conversation with {len(history_messages)} previous messages")

            llm_manager = LLMManager()
            llm_manager.set_llm(llm)
            instructions_manager = InstructionsManager()

            instructions_to_use = self.instructions or ""
            logger.debug(f"[CUGA] instructions are: {instructions_to_use}")
            instructions_manager.set_instructions_from_one_file(instructions_to_use)
            tracker = ActivityTracker()
            tracker.set_tools(tools)
            thread_id = self.graph.session_id
            logger.debug(f"[CUGA] Using thread_id (session_id): {thread_id}")
            cuga_agent = CugaAgent(browser_enabled=self.browser_enabled, thread_id=thread_id)
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
                logger.debug(f"[CUGA] Converting {len(history_messages)} history messages to LangChain format")
                lc_messages = []
                for i, msg in enumerate(history_messages):
                    msg_text = getattr(msg, "text", "N/A")[:50] if hasattr(msg, "text") else "N/A"
                    logger.debug(
                        f"[CUGA] Message {i}: type={type(msg)}, sender={getattr(msg, 'sender', 'N/A')}, "
                        f"text={msg_text}..."
                    )
                    if hasattr(msg, "sender") and msg.sender == "Human":
                        lc_messages.append(HumanMessage(content=msg.text))
                    else:
                        lc_messages.append(AIMessage(content=msg.text))

                logger.debug(f"[CUGA] Converted to {len(lc_messages)} LangChain messages")
                await asyncio.sleep(0.5)

                # 2. Build final response
                response_parts = []

                response_parts.append(f"Processed input: '{current_input}'")
                response_parts.append(f"Available tools: {len(tools)}")
                last_event: StreamEvent | None = None
                tool_run_id: str | None = None
                # 3. Chain end event with AgentFinish
                async for event in cuga_agent.run_task_generic_yield(
                    eval_mode=False, goal=current_input, chat_messages=lc_messages
                ):
                    logger.debug(f"[CUGA] recieved event {event}")
                    if last_event is not None and tool_run_id is not None:
                        logger.debug(f"[CUGA] last event {last_event}")
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
                logger.error(f"[CUGA] An error occurred: {e!s}")
                logger.error(f"[CUGA] Traceback: {traceback.format_exc()}")
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
            from lfx.schema.content_block import ContentBlock
            from lfx.schema.message import MESSAGE_SENDER_AI

            llm_model, self.chat_history, self.tools = await self.get_agent_requirements()

            # Create agent message for event processing
            agent_message = Message(
                sender=MESSAGE_SENDER_AI,
                sender_name="Cuga",
                properties={"icon": "Bot", "state": "partial"},
                content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
                session_id=self.graph.session_id,
            )

            # Pre-assign an ID for event processing, following the base agent pattern
            # This ensures streaming works even when not connected to ChatOutput
            if not self.is_connected_to_chat_output():
                # When not connected to ChatOutput, assign ID upfront for streaming support
                agent_message.data["id"] = uuid.uuid4()

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

                logger.debug(f"[CUGA] Message processed with ID: {result.id}")
                return result

            result = await process_agent_events(
                event_iterator, agent_message, cast("SendMessageFunctionType", force_db_update_send_message)
            )

            logger.debug("[CUGA] Agent run finished successfully.")
            logger.debug(f"[CUGA] Agent output: {result}")

        except Exception as e:
            logger.error(f"[CUGA] Error in message_response: {e}")
            logger.error(f"[CUGA] An error occurred: {e!s}")
            logger.error(f"[CUGA] Traceback: {traceback.format_exc()}")

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

    async def get_memory_data(self):
        """Retrieve chat history messages.

        This method fetches the conversation history from memory, excluding the current
        input message to avoid duplication.

        Returns:
            list: List of Message objects representing the chat history
        """
        logger.debug("[CUGA] Retrieving chat history messages.")
        logger.debug(f"[CUGA] Session ID: {self.graph.session_id}")
        logger.debug(f"[CUGA] n_messages: {self.n_messages}")
        logger.debug(f"[CUGA] input_value: {self.input_value}")
        logger.debug(f"[CUGA] input_value type: {type(self.input_value)}")
        logger.debug(f"[CUGA] input_value id: {getattr(self.input_value, 'id', None)}")

        messages = (
            await MemoryComponent(**self.get_base_args())
            .set(session_id=str(self.graph.session_id), order="Ascending", n_messages=self.n_messages)
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
        logger.debug(f"[CUGA] Requested LLM model: {self.model}")

        try:
            llm_model = get_llm(
                model=self.model,
                user_id=self.user_id,
                api_key=getattr(self, "api_key", None),
            )
            if llm_model is None:
                msg = "No language model selected. Please choose a model to proceed."
                raise ValueError(msg)

            display_name = None
            if isinstance(self.model, list) and len(self.model) > 0:
                display_name = self.model[0].get("name")

            logger.debug(f"[CUGA] Successfully built LLM model: {display_name}")
        except (AttributeError, ValueError, TypeError, RuntimeError) as e:
            logger.error(f"[CUGA] Error building language model: {e!s}")
            msg = f"Failed to initialize language model: {e!s}"
            raise ValueError(msg) from e
        else:
            return llm_model, display_name

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
        self,
        build_config: dotdict,
        field_value: list[dict],
        field_name: str | None = None,
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

        # Iterate over all providers
        if field_name == "model":
            self.log(str(field_value))
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
                "instructions",
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
