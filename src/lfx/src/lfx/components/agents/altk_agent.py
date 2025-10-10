import ast
import json
import uuid
from typing import TYPE_CHECKING, Any, cast

from altk.post_tool_reflection_toolkit.code_generation.code_generation import (
    CodeGenerationComponent,
    CodeGenerationComponentConfig,
)
from altk.post_tool_reflection_toolkit.core.toolkit import CodeGenerationRunInput
from altk.toolkit_core.core.toolkit import AgentPhase
from altk.toolkit_core.llm import get_llm
from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.callbacks.base import BaseCallbackHandler
from langchain_anthropic.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableBinding
from langchain_openai.chat_models.base import ChatOpenAI

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.utils import data_to_messages
from lfx.base.models.model_input_constants import (
    MODEL_PROVIDERS_DICT,
    MODELS_METADATA,
)
from lfx.components.agents import AgentComponent
from lfx.components.helpers.memory import MemoryComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import DropdownInput, IntInput, MultilineInput, Output, TableInput
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.schema.table import EditMode
from lfx.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from lfx.schema.log import SendMessageFunctionType


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]


class PostToolCallbackHandler(BaseCallbackHandler):
    """A callback handler to process tool outputs.

    This callback handler overrides the on_tool_end method and
    if the tool output is a JSON, it invokes an ALTK component
    to extract information from the JSON by generating Python code.
    """

    def __init__(self, user_query: str, agent: Runnable, response_processing_size_threshold: int):
        self.user_query = user_query
        self.agent = agent
        self.response_processing_size_threshold = response_processing_size_threshold

    def _get_tool_response_str(self, tool_response) -> str | None:
        if isinstance(tool_response, str):
            tool_response_str = tool_response
        elif isinstance(tool_response, (dict, list)):
            tool_response_str = str(tool_response)
        elif isinstance(tool_response, Data):
            tool_response_str = str(tool_response.data)
        elif isinstance(tool_response, list) and all(isinstance(item, Data) for item in tool_response):
            # get only the first element, not 100% sure if it should be the first or the last
            tool_response_str = str(tool_response[0].data)
        else:
            tool_response_str = None
        return tool_response_str

    def _get_altk_llm_object(self) -> Any:
        # Extract the LLM model and map it to altk model inputs
        for step in self.agent.steps:
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

    def on_tool_end(self, tool_response: str, **_kwargs) -> None:
        logger.info("Calling on_tool_end of PostToolCallbackHandler")
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
                nl_query = self.user_query
                input_data = CodeGenerationRunInput(messages=[], nl_query=nl_query, tool_response=tool_response_json)
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

    display_name: str = "ALTKAgent"
    description: str = "Agent with enhanced tool calling capabilities. For more information on ALTK, visit https://github.com/AgentToolkit/agent-lifecycle-toolkit"
    documentation: str = "https://docs.langflow.org/agents"
    icon = "bot"
    beta = True
    name = "ALTKAgent"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

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
            external_options={
                "fields": {
                    "data": {
                        "node": {
                            "name": "connect_other_models",
                            "display_name": "Connect other models",
                            "icon": "CornerDownLeft",
                        }
                    }
                },
            },
        ),
        *openai_inputs_filtered,
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
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
        *LCToolsAgentComponent._base_inputs,
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
            name="enable_post_tool_reflection",
            display_name="Post Tool Processing",
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
                return_intermediate_steps=True,
            )
        input_dict: dict[str, str | list[BaseMessage]] = {
            "input": self.input_value.to_lc_message() if isinstance(self.input_value, Message) else self.input_value
        }
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt
        if hasattr(self, "chat_history") and self.chat_history:
            if isinstance(self.chat_history, Data):
                input_dict["chat_history"] = data_to_messages(self.chat_history)
            if all(isinstance(m, Message) for m in self.chat_history):
                input_dict["chat_history"] = data_to_messages([m.to_data() for m in self.chat_history])
        if hasattr(input_dict["input"], "content") and isinstance(input_dict["input"].content, list):
            # ! Because the input has to be a string, we must pass the images in the chat_history

            image_dicts = [item for item in input_dict["input"].content if item.get("type") == "image"]
            input_dict["input"].content = [item for item in input_dict["input"].content if item.get("type") != "image"]

            if "chat_history" not in input_dict:
                input_dict["chat_history"] = []
            if isinstance(input_dict["chat_history"], list):
                input_dict["chat_history"].extend(HumanMessage(content=[image_dict]) for image_dict in image_dicts)
            else:
                input_dict["chat_history"] = [HumanMessage(content=[image_dict]) for image_dict in image_dicts]

        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=self.display_name or "Agent",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )
        try:
            callbacks_to_be_used = [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]
            if self.enable_post_tool_reflection:
                if hasattr(input_dict["input"], "content"):
                    callbacks_to_be_used.append(
                        PostToolCallbackHandler(
                            input_dict["input"].content, agent, self.response_processing_size_threshold
                        )
                    )
                elif isinstance(input_dict["input"], str):
                    callbacks_to_be_used.append(
                        PostToolCallbackHandler(input_dict["input"], agent, self.response_processing_size_threshold)
                    )

            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={"callbacks": callbacks_to_be_used},
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
