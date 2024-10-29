from langflow.base.models.model import LCModelComponent
from langflow.components.agents.tool_calling import ToolCallingAgentComponent
from langflow.components.models.azure_openai import AzureChatOpenAIComponent
from langflow.components.models.openai import OpenAIModelComponent
from langflow.io import (
    DataInput,
    DropdownInput,
    HandleInput,
    MessageTextInput,
    Output,
)
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message


class SimpleAgentComponent(ToolCallingAgentComponent):
    display_name: str = "Simple Agent"
    description: str = "Agent that uses tools"
    icon = "workflow"
    beta = True
    name = "SimpleAgent"
    AZURE_OPENAI_API_VERSIONS = [
        "2024-06-01",
        "2024-07-01-preview",
        "2024-08-01-preview",
        "2024-09-01-preview",
        "2024-10-01-preview",
        "2023-05-15",
        "2023-12-01-preview",
        "2024-02-15-preview",
        "2024-03-01-preview",
    ]

    openai_inputs = [
        component_input
        for component_input in OpenAIModelComponent().inputs
        if component_input.name not in [input_field.name for input_field in LCModelComponent._base_inputs]
    ]
    azure_inputs = [
        component_input
        for component_input in AzureChatOpenAIComponent().inputs
        if component_input.name not in [input_field.name for input_field in LCModelComponent._base_inputs]
    ]
    inputs = [
        HandleInput(
            name="tools", display_name="Tools", input_types=["Tool", "BaseTool", "StructuredTool"], is_list=True
        ),
        MessageTextInput(name="input_value", display_name="Input"),
        DataInput(name="chat_history", display_name="Chat History", is_list=True, advanced=True),
        DropdownInput(
            name="agent_llm",
            display_name="Language Model Type",
            options=["Azure OpenAI", "OpenAI"],
            value="OpenAI",
            real_time_refresh=True,
            input_types=["LanguageModel"],
            refresh_button=True
        ),
        *openai_inputs,
    ]
    outputs = [Output(name="response", display_name="Response", method="get_response")]

    async def get_response(self) -> Message:
        llm_model = self.get_llm()
        if llm_model is None:
            msg = "No language model selected"
            raise ValueError(msg)

        agent = ToolCallingAgentComponent().set(
            llm=llm_model, tools=[self.tools], chat_history=self.chat_history, input_value=self.input_value
        )

        return await agent.message_response()

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

            elif field_value == "Azure OpenAI":
                self.delete_fields(build_config, {**openai_fields})
                build_config.update(azure_fields)
            elif field_value == "Custom":
                self.delete_fields(build_config, {**openai_fields})
                self.delete_fields(build_config, {**azure_fields})

        default_keys = ["code", "_type", "agent_llm", "tools", "input_value"]
        missing_keys = [key for key in default_keys if key not in build_config]
        if missing_keys:
            msg = f"Missing required keys in build_config: {missing_keys}"
            raise ValueError(msg)
        #debug code
        for key, value in build_config.items():
            if isinstance(value, dict) and value.get("input_types") is None and key not in ["code", "_type"]:
                msg = f"Component {key} has no input types specified"
                raise ValueError(msg)
        return build_config
