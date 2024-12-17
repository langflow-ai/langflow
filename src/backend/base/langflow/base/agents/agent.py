import re
from abc import abstractmethod
from typing import TYPE_CHECKING, cast

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.agents.agent import RunnableAgent
from langchain_core.runnables import Runnable

from langflow.base.agents.callback import AgentAsyncHandler
from langflow.base.agents.events import ExceptionWithMessageError, process_agent_events
from langflow.base.agents.utils import data_to_messages
from langflow.base.models.model_input_constants import ALL_PROVIDER_FIELDS, MODEL_PROVIDERS_DICT
from langflow.custom import Component
from langflow.custom.custom_component.component import _get_component_toolkit
from langflow.custom.utils import update_component_build_config
from langflow.field_typing import Tool
from langflow.inputs.inputs import DropdownInput, InputTypes, MultilineInput
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput
from langflow.memory import delete_message
from langflow.schema import Data, dotdict
from langflow.schema.content_block import ContentBlock
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

    from langflow.schema.log import SendMessageFunctionType


DEFAULT_TOOLS_DESCRIPTION = "A helpful assistant with access to the following tools:"
DEFAULT_AGENT_NAME = "Agent ({tools_names})"


class LCAgentComponent(Component):
    trace_type = "agent"
    _base_inputs: list[InputTypes] = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="The input provided by the user for the agent to process.",
            tool_mode=True,
        ),
        BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
            info="Should the Agent fix errors when reading user input for better processing?",
        ),
        BoolInput(name="verbose", display_name="Verbose", value=True, advanced=True),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=15,
            advanced=True,
            info="The maximum number of attempts the agent can make to complete its task before it stops.",
        ),
        MultilineInput(
            name="agent_description",
            display_name="Agent Description [Deprecated]",
            info=(
                "The description of the agent. This is only used when in Tool Mode. "
                f"Defaults to '{DEFAULT_TOOLS_DESCRIPTION}' and tools are added dynamically. "
                "This feature is deprecated and will be removed in future versions."
            ),
            advanced=True,
            value=DEFAULT_TOOLS_DESCRIPTION,
        ),
    ]

    outputs = [
        Output(display_name="Agent", name="agent", method="build_agent"),
        Output(display_name="Response", name="response", method="message_response"),
    ]

    @abstractmethod
    def build_agent(self) -> AgentExecutor:
        """Create the agent."""

    async def message_response(self) -> Message:
        """Run the agent and return the response."""
        agent = self.build_agent()
        message = await self.run_agent(agent=agent)

        self.status = message
        return message

    def _validate_outputs(self) -> None:
        required_output_methods = ["build_agent"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                msg = f"Output with name '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)

    def get_agent_kwargs(self, *, flatten: bool = False) -> dict:
        base = {
            "handle_parsing_errors": self.handle_parsing_errors,
            "verbose": self.verbose,
            "allow_dangerous_code": True,
        }
        agent_kwargs = {
            "handle_parsing_errors": self.handle_parsing_errors,
            "max_iterations": self.max_iterations,
        }
        if flatten:
            return {
                **base,
                **agent_kwargs,
            }
        return {**base, "agent_executor_kwargs": agent_kwargs}

    def get_chat_history_data(self) -> list[Data] | None:
        # might be overridden in subclasses
        return None

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            if not hasattr(self, "tools") or not self.tools:
                msg = "Tools are required to run the agent."
                raise ValueError(msg)
            handle_parsing_errors = hasattr(self, "handle_parsing_errors") and self.handle_parsing_errors
            verbose = hasattr(self, "verbose") and self.verbose
            max_iterations = hasattr(self, "max_iterations") and self.max_iterations
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=self.tools,
                handle_parsing_errors=handle_parsing_errors,
                verbose=verbose,
                max_iterations=max_iterations,
            )
        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt
        if hasattr(self, "chat_history") and self.chat_history:
            input_dict["chat_history"] = data_to_messages(self.chat_history)

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
            session_id=session_id,
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
            msg_id = e.agent_message.id
            await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            raise
        except Exception:
            raise

        self.status = result
        return result

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""

    def validate_tool_names(self) -> None:
        """Validate tool names to ensure they match the required pattern."""
        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
        if hasattr(self, "tools") and self.tools:
            for tool in self.tools:
                if not pattern.match(tool.name):
                    msg = (
                        f"Invalid tool name '{tool.name}': must only contain letters, numbers, underscores, dashes,"
                        " and cannot contain spaces."
                    )
                    raise ValueError(msg)


class LCToolsAgentComponent(LCAgentComponent):
    _base_inputs = [
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool", "BaseTool", "StructuredTool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
        *LCAgentComponent._base_inputs,
    ]

    def build_agent(self) -> AgentExecutor:
        self.validate_tool_names()
        agent = self.create_agent_runnable()
        return AgentExecutor.from_agent_and_tools(
            agent=RunnableAgent(runnable=agent, input_keys_arg=["input"], return_keys_arg=["output"]),
            tools=self.tools,
            **self.get_agent_kwargs(flatten=True),
        )

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""

    def get_tool_name(self) -> str:
        return self.display_name or "Agent"

    def get_tool_description(self) -> str:
        return self.agent_description or DEFAULT_TOOLS_DESCRIPTION

    def _build_tools_names(self):
        tools_names = ""
        if self.tools:
            tools_names = ", ".join([tool.name for tool in self.tools])
        return tools_names

    def to_toolkit(self) -> list[Tool]:
        component_toolkit = _get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        # TODO: Agent Description Depreciated Feature to be removed
        description = f"{agent_description}{tools_names}"
        tools = component_toolkit(component=self).get_tools(
            tool_name=self.get_tool_name(), tool_description=description, callbacks=self.get_langchain_callbacks()
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)
        return tools


class LangflowAgent(LCToolsAgentComponent):
    llm = None
    chat_history = None
    _agentbase_inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            info="The provider of the language model that the agent will use to generate responses.",
            options=[*sorted(MODEL_PROVIDERS_DICT.keys()), "Custom"],
            value="OpenAI",
            real_time_refresh=True,
            input_types=[],
        ),
        *MODEL_PROVIDERS_DICT["OpenAI"]["inputs"],
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
            advanced=False,
        ),
        *LCToolsAgentComponent._base_inputs,
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
    ]

    async def update_build_config(
        self, build_config: dotdict, field_value: str, field_name: str | None = None
    ) -> dotdict:
        # Iterate over all providers in the MODEL_PROVIDERS_DICT
        # Existing logic for updating build_config
        if field_name == "agent_llm":
            provider_info = MODEL_PROVIDERS_DICT.get(field_value)
            if provider_info:
                component_class = provider_info.get("component_class")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call the component class's update_build_config method
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, field_name
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
                # Reset input types for agent_llm
                build_config["agent_llm"]["input_types"] = []
            elif field_value == "Custom":
                # Delete all provider fields
                self.delete_fields(build_config, ALL_PROVIDER_FIELDS)
                # Update with custom component
                custom_component = DropdownInput(
                    name="agent_llm",
                    display_name="Language Model",
                    options=[*sorted(MODEL_PROVIDERS_DICT.keys()), "Custom"],
                    value="Custom",
                    real_time_refresh=True,
                    input_types=["LanguageModel"],
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
        if isinstance(self.agent_llm, str) and self.agent_llm in MODEL_PROVIDERS_DICT:
            provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
            if provider_info:
                component_class = provider_info.get("component_class")
                prefix = provider_info.get("prefix")
                if component_class and hasattr(component_class, "update_build_config"):
                    # Call each component class's update_build_config method
                    # remove the prefix from the field_name
                    if isinstance(field_name, str) and isinstance(prefix, str):
                        field_name = field_name.replace(prefix, "")
                    build_config = await update_component_build_config(
                        component_class, build_config, field_value, field_name
                    )

        return build_config

    def get_llm(self):
        if isinstance(self.agent_llm, str):
            try:
                provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
                if provider_info:
                    component_class = provider_info.get("component_class")
                    display_name = component_class.display_name
                    inputs = provider_info.get("inputs")
                    prefix = provider_info.get("prefix", "")
                    return (
                        self._build_llm_model(component_class, inputs, prefix),
                        display_name,
                    )
            except Exception as e:
                msg = f"Error building {self.agent_llm} language model"
                raise ValueError(msg) from e
        return self.agent_llm, None

    def _build_llm_model(self, component, inputs, prefix=""):
        model_kwargs = {input_.name: getattr(self, f"{prefix}{input_.name}") for input_ in inputs}
        return component.set(**model_kwargs).build_model()

    def delete_fields(self, build_config: dotdict, fields: dict | list[str]) -> None:
        """Delete specified fields from build_config."""
        for field in fields:
            build_config.pop(field, None)

    def update_input_types(self, build_config: dotdict) -> dotdict:
        """Update input types for all fields in build_config."""
        for key, value in build_config.items():
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config

    @abstractmethod
    async def message_response(self) -> Message:
        """Run the agent and return the response."""
