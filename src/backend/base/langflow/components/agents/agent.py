from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.base.models.model import LCModelComponent
from langflow.components.agents.tool_calling import ToolCallingAgentComponent
from langflow.components.helpers.memory import MemoryComponent
from langflow.components.models.azure_openai import AzureChatOpenAIComponent
from langflow.components.models.openai import OpenAIModelComponent
from langflow.io import (
    DropdownInput,
    MultilineInput,
    Output,
)
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


class AgentComponent(ToolCallingAgentComponent):
    display_name: str = "Agent"
    description: str = "Define the agent's instructions, then enter a task to complete using tools."
    icon = "bot"
    beta = True
    name = "Agent"

    azure_inputs = [
        set_advanced_true(component_input) if component_input.name == "temperature" else component_input
        for component_input in AzureChatOpenAIComponent().inputs
        if component_input.name not in [input_field.name for input_field in LCModelComponent._base_inputs]
    ]
    openai_inputs = [
        set_advanced_true(component_input) if component_input.name == "temperature" else component_input
        for component_input in OpenAIModelComponent().inputs
        if component_input.name not in [input_field.name for input_field in LCModelComponent._base_inputs]
    ]

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            options=["Azure OpenAI", "OpenAI", "Custom"],
            value="OpenAI",
            real_time_refresh=True,
            refresh_button=True,
            input_types=[],
        ),
        *openai_inputs,
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="Initial instructions and context provided to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
            advanced=False,
        ),
        *LCToolsAgentComponent._base_inputs,
        *memory_inputs,
    ]
    outputs = [Output(name="response", display_name="Response", method="get_response")]

    async def get_response(self) -> Message:
        llm_model = self.get_llm()
        if llm_model is None:
            msg = "No language model selected"
            raise ValueError(msg)
        self.chat_history = self.get_memory_data()

        agent = ToolCallingAgentComponent().set(
            llm=llm_model,
            tools=[self.tools],
            chat_history=self.chat_history,
            input_value=self.input_value,
            system_prompt=self.system_prompt,
        )

        return await agent.message_response()

    def get_memory_data(self):
        memory_kwargs = {
            component_input.name: getattr(self, f"{component_input.name}") for component_input in self.memory_inputs
        }

        return MemoryComponent().set(**memory_kwargs).retrieve_messages()

    def get_llm(self):
        try:
            if self.agent_llm == "OpenAI":
                return self._build_llm_model(OpenAIModelComponent(), self.openai_inputs)
            if self.agent_llm == "Azure OpenAI":
                return self._build_llm_model(AzureChatOpenAIComponent(), self.azure_inputs, prefix="azure_param_")
        except Exception as e:
            msg = f"Error building {self.agent_llm} language model"
            raise ValueError(msg) from e
        return self.agent_llm

    def _build_llm_model(self, component, inputs, prefix=""):
        return component.set(
            **{component_input.name: getattr(self, f"{prefix}{component_input.name}") for component_input in inputs}
        ).build_model()

    def delete_fields(self, build_config, fields):
        for field in fields:
            build_config.pop(field, None)

    def update_build_config(self, build_config: dotdict, field_value: str, field_name: str | None = None):
        if field_name == "agent_llm":
            openai_fields = {component_input.name: component_input for component_input in self.openai_inputs}
            azure_fields = {
                f"azure_param_{component_input.name}": component_input for component_input in self.azure_inputs
            }

            if field_value == "OpenAI":
                self.delete_fields(build_config, {**azure_fields})
                if not any(field in build_config for field in openai_fields):
                    build_config.update(openai_fields)
                build_config["agent_llm"]["input_types"] = []
                build_config = self.update_input_types(build_config)

            elif field_value == "Azure OpenAI":
                self.delete_fields(build_config, {**openai_fields})
                build_config.update(azure_fields)
                build_config["agent_llm"]["input_types"] = []
                build_config = self.update_input_types(build_config)
            elif field_value == "Custom":
                self.delete_fields(build_config, {**openai_fields})
                self.delete_fields(build_config, {**azure_fields})
                new_component = DropdownInput(
                    name="agent_llm",
                    display_name="Language Model",
                    options=["Azure OpenAI", "OpenAI", "Custom"],
                    value="Custom",
                    real_time_refresh=True,
                    input_types=["LanguageModel"],
                )
                build_config.update({"agent_llm": new_component.to_dict()})
                build_config = self.update_input_types(build_config)
            default_keys = ["code", "_type", "agent_llm", "tools", "input_value"]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
        return build_config

    def update_input_types(self, build_config):
        for key, value in build_config.items():
            # Check if the value is a dictionary
            if isinstance(value, dict):
                if value.get("input_types") is None:
                    build_config[key]["input_types"] = []
            # Check if the value has an attribute 'input_types' and it is None
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []
        return build_config
