import ast
import json
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from altk.core.llm import get_llm
from altk.core.toolkit import AgentPhase
from altk.post_tool.code_generation.code_generation import (
    CodeGenerationComponent,
    CodeGenerationComponentConfig,
)
from altk.post_tool.core.toolkit import CodeGenerationRunInput
from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableBinding
from langchain_core.tools import BaseTool
from langchain_openai.chat_models.base import ChatOpenAI
from pydantic import Field

from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.utils import data_to_messages, get_chat_output_sender_name
from lfx.base.models.model_input_constants import (
    MODEL_PROVIDERS_DICT,
    MODELS_METADATA,
)
from lfx.components.agents import AgentComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import DropdownInput, IntInput, Output
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from lfx.schema.log import SendMessageFunctionType


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]
INPUT_NAMES_TO_BE_OVERRIDDEN = ["agent_llm"]


def get_parent_agent_inputs():
    return [
        input_field for input_field in AgentComponent.inputs if input_field.name not in INPUT_NAMES_TO_BE_OVERRIDDEN
    ]


class PostToolProcessor(BaseTool):
    """A tool output processor to process tool outputs.

    This wrapper intercepts the tool execution output and
    if the tool output is a JSON, it invokes an ALTK component
    to extract information from the JSON by generating Python code.
    """

    name: str = Field(...)
    description: str = Field(...)
    wrapped_tool: BaseTool = Field(...)
    user_query: str = Field(...)
    agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor = Field(...)
    response_processing_size_threshold: int = Field(...)

    def __init__(
        self, wrapped_tool: BaseTool, user_query: str, agent, response_processing_size_threshold: int, **kwargs
    ):
        super().__init__(
            name=wrapped_tool.name,
            description=wrapped_tool.description,
            wrapped_tool=wrapped_tool,
            user_query=user_query,
            agent=agent,
            response_processing_size_threshold=response_processing_size_threshold,
            **kwargs,
        )

    def _execute_tool(self, *args, **kwargs) -> str:
        """Execute the wrapped tool with proper error handling."""
        try:
            # Try with config parameter first (newer LangChain versions)
            if hasattr(self.wrapped_tool, "_run"):
                # Ensure config is provided for StructuredTool
                if "config" not in kwargs:
                    kwargs["config"] = {}
                return self.wrapped_tool._run(*args, **kwargs)  # noqa: SLF001
            return self.wrapped_tool.run(*args, **kwargs)
        except TypeError as e:
            if "config" in str(e):
                # Fallback: try without config for older tools
                kwargs.pop("config", None)
                if hasattr(self.wrapped_tool, "_run"):
                    return self.wrapped_tool._run(*args, **kwargs)  # noqa: SLF001
                return self.wrapped_tool.run(*args, **kwargs)
            raise

    def _run(self, *args: Any, **kwargs: Any) -> str:
        # Run the wrapped tool
        result = self._execute_tool(*args, **kwargs)

        # Run postprocessing and return the output
        return self.process_tool_response(result)

    def _get_tool_response_str(self, tool_response) -> str | None:
        if isinstance(tool_response, str):
            tool_response_str = tool_response
        elif isinstance(tool_response, Data):
            tool_response_str = str(tool_response.data)
        elif isinstance(tool_response, list) and all(isinstance(item, Data) for item in tool_response):
            # get only the first element, not 100% sure if it should be the first or the last
            tool_response_str = str(tool_response[0].data)
        elif isinstance(tool_response, (dict, list)):
            tool_response_str = str(tool_response)
        else:
            tool_response_str = None
        return tool_response_str

    def _get_altk_llm_object(self) -> Any:
        # Extract the LLM model and map it to altk model inputs
        llm_object: BaseChatModel | None = None
        steps = getattr(self.agent, "steps", None)
        if steps:
            for step in steps:
                if isinstance(step, RunnableBinding) and isinstance(step.bound, BaseChatModel):
                    llm_object = step.bound
                    break
        if isinstance(llm_object, ChatAnthropic):
            # litellm needs the prefix to the model name for anthropic
            model_name = f"anthropic/{llm_object.model}"
            api_key = llm_object.anthropic_api_key.get_secret_value()
            llm_client = get_llm("litellm")
            llm_client_obj = llm_client(model_name=model_name, api_key=api_key)
        elif isinstance(llm_object, ChatOpenAI):
            model_name = llm_object.model_name
            api_key = llm_object.openai_api_key.get_secret_value()
            llm_client = get_llm("openai.sync")
            llm_client_obj = llm_client(model=model_name, api_key=api_key)
        else:
            logger.info("ALTK currently only supports OpenAI and Anthropic models through Langflow.")
            llm_client_obj = None

        return llm_client_obj

    def process_tool_response(self, tool_response: str, **_kwargs):
        logger.info("Calling process_tool_response of PostToolProcessor")
        tool_response_str = self._get_tool_response_str(tool_response)

        try:
            tool_response_json = ast.literal_eval(tool_response_str)
            if not isinstance(tool_response_json, (list, dict)):
                tool_response_json = None
        except (json.JSONDecodeError, TypeError) as e:
            logger.info(
                f"An error in converting the tool response to json, this will skip the code generation component: {e}"
            )
            tool_response_json = None

        if tool_response_json is not None and len(str(tool_response_json)) > self.response_processing_size_threshold:
            llm_client_obj = self._get_altk_llm_object()
            if llm_client_obj is not None:
                config = CodeGenerationComponentConfig(llm_client=llm_client_obj, use_docker_sandbox=False)

                middleware = CodeGenerationComponent(config=config)
                input_data = CodeGenerationRunInput(
                    messages=[], nl_query=self.user_query, tool_response=tool_response_json
                )
                output = None
                try:
                    output = middleware.process(input_data, AgentPhase.RUNTIME)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Exception in executing CodeGenerationComponent: {e}")
                logger.info(f"Output of CodeGenerationComponent: {output.result}")
                return output.result
        return tool_response


class ALTKAgentComponent(AgentComponent):
    """An advanced tool calling agent.

    The ALTKAgent is an advanced AI agent that enhances the tool calling capabilities of LLMs
    by performing special checks and processing around tool calls.
    It uses components from the Agent Lifecycle ToolKit (https://github.com/AgentToolkit/agent-lifecycle-toolkit)
    """

    display_name: str = "ALTK Agent"
    description: str = "Agent with enhanced tool calling capabilities. For more information on ALTK, visit https://github.com/AgentToolkit/agent-lifecycle-toolkit"
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    beta = True
    name = "ALTKAgent"

    # Filter out json_mode from OpenAI inputs since we handle structured output differently
    if "OpenAI" in MODEL_PROVIDERS_DICT:
        openai_inputs_filtered = [
            input_field
            for input_field in MODEL_PROVIDERS_DICT["OpenAI"]["inputs"]
            if not (hasattr(input_field, "name") and input_field.name == "json_mode")
        ]
    else:
        openai_inputs_filtered = []

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            info="The provider of the language model that the agent will use to generate responses.",
            options=[*MODEL_PROVIDERS_LIST],
            value="OpenAI",
            real_time_refresh=True,
            refresh_button=False,
            input_types=[],
            options_metadata=[MODELS_METADATA[key] for key in MODEL_PROVIDERS_LIST if key in MODELS_METADATA],
        ),
        *get_parent_agent_inputs(),
        BoolInput(
            name="enable_post_tool_reflection",
            display_name="Post Tool JSON Processing",
            info="If true, it passes the tool output to a json processing (if json) step.",
            value=True,
        ),
        # Post Tool Processing is applied only when the number of characters in the response
        # exceed the following threshold
        IntInput(
            name="response_processing_size_threshold",
            display_name="Response Processing Size Threshold",
            value=100,
            info="Tool output is post-processed only if the response length exceeds a specified character threshold.",
            advanced=True,
            show=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    def update_runnable_instance(
        self, agent: AgentExecutor, runnable: AgentExecutor, tools: Sequence[BaseTool]
    ) -> AgentExecutor:
        user_query = self.input_value.get_text() if hasattr(self.input_value, "get_text") else self.input_value
        if self.enable_post_tool_reflection:
            wrapped_tools = [
                PostToolProcessor(
                    wrapped_tool=tool,
                    user_query=user_query,
                    agent=agent,
                    response_processing_size_threshold=self.response_processing_size_threshold,
                )
                if not isinstance(tool, PostToolProcessor)
                else tool
                for tool in tools
            ]
        else:
            wrapped_tools = tools

        runnable.tools = wrapped_tools

        return runnable

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            # note the tools are not required to run the agent, hence the validation removed.
            handle_parsing_errors = hasattr(self, "handle_parsing_errors") and self.handle_parsing_errors
            verbose = hasattr(self, "verbose") and self.verbose
            max_iterations = hasattr(self, "max_iterations") and self.max_iterations
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=self.tools or [],
                handle_parsing_errors=handle_parsing_errors,
                verbose=verbose,
                max_iterations=max_iterations,
            )
        runnable = self.update_runnable_instance(agent, runnable, self.tools)

        # Convert input_value to proper format for agent
        if hasattr(self.input_value, "to_lc_message") and callable(self.input_value.to_lc_message):
            lc_message = self.input_value.to_lc_message()
            input_text = lc_message.content if hasattr(lc_message, "content") else str(lc_message)
        else:
            lc_message = None
            input_text = self.input_value

        input_dict: dict[str, str | list[BaseMessage]] = {}
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt
        if hasattr(self, "chat_history") and self.chat_history:
            if (
                hasattr(self.chat_history, "to_data")
                and callable(self.chat_history.to_data)
                and self.chat_history.__class__.__name__ == "Data"
            ):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            # Handle both lfx.schema.message.Message and langflow.schema.message.Message types
            if all(hasattr(m, "to_data") and callable(m.to_data) and "text" in m.data for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            if all(isinstance(m, Message) for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages([m.to_data() for m in self.chat_history])
        if hasattr(lc_message, "content") and isinstance(lc_message.content, list):
            # ! Because the input has to be a string, we must pass the images in the chat_history

            image_dicts = [item for item in lc_message.content if item.get("type") == "image"]
            lc_message.content = [item for item in lc_message.content if item.get("type") != "image"]

            if "chat_history" not in input_dict:
                input_dict["chat_history"] = []
            if isinstance(input_dict["chat_history"], list):
                input_dict["chat_history"].extend(HumanMessage(content=[image_dict]) for image_dict in image_dicts)
            else:
                input_dict["chat_history"] = [HumanMessage(content=[image_dict]) for image_dict in image_dicts]
        input_dict["input"] = input_text
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        try:
            sender_name = get_chat_output_sender_name(self)
        except AttributeError:
            sender_name = self.display_name or "AI"

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=sender_name,
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )
        try:
            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]},
                    version="v2",
                ),
                agent_message,
                cast("SendMessageFunctionType", self.send_message),
            )
        except ExceptionWithMessageError as e:
            if hasattr(e, "agent_message") and hasattr(e.agent_message, "id"):
                msg_id = e.agent_message.id
                await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            logger.error(f"ExceptionWithMessageError: {e}")
            raise
        except Exception as e:
            # Log or handle any other exceptions
            logger.error(f"Error: {e}")
            raise

        self.status = result
        return result
