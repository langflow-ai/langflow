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
            options=["Custom", "Azure OpenAI", "OpenAI"],
            value="OpenAI",
            real_time_refresh=True,
        ),
        *openai_inputs,
    ]
    outputs = [Output(name="response", display_name="Response", method="get_response")]

    async def get_response(self) -> Message:
        # Chat input initialization

        # Default OpenAI Model Component
        llm_model = self.get_llm()
        if llm_model is None:
            msg = "No language model selected"
            raise ValueError(msg)

        agent = ToolCallingAgentComponent().set(
            llm=llm_model, tools=[self.tools], chat_history=self.chat_history, input_value=self.input_value
        )

        return await agent.message_response()

    def get_llm(self):
        if self.agent_llm == "OpenAI":
            return (
                OpenAIModelComponent()
                .set(
                    **{
                        component_input.name: getattr(self, component_input.name)
                        for component_input in self.openai_inputs
                    }
                )
                .build_model()
            )
        if self.agent_llm == "Azure OpenAI":
            return (
                AzureChatOpenAIComponent()
                .set(
                    **{
                        component_input.name: getattr(self, f"azure_param_{component_input.name}")
                        for component_input in self.azure_inputs
                    }
                )
                .build_model()
            )
        if self.agent_llm == "Custom":
            return self.llm_custom
        return None

    def insert_in_dict(self, build_config, field_name, new_parameters):
        # Insert the new key-value pair after the found key
        for new_field_name, new_parameter in new_parameters.items():
            # Get all the items as a list of tuples (key, value)
            items = list(build_config.items())

            # Find the index of the key to insert after
            idx = len(items)
            for i, (key, _value) in enumerate(items):
                if key == field_name:
                    idx = i + 1
                    break

            items.insert(idx, (new_field_name, new_parameter))

            # Clear the original dictionary and update with the modified items
            build_config.clear()
            build_config.update(items)

        return build_config

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name == "agent_llm":
            openai_fields = {component.name: component for component in self.openai_inputs}
            azure_fields = {f"azure_param_{component.name}": component for component in self.azure_inputs}
            if field_value == "OpenAI":
                for field in [key for key in build_config if key.startswith("azure_param_")]:
                    if field in build_config:
                        del build_config[field]
                for field in openai_fields:
                    if field in build_config:
                        del build_config[field]
                if "llm_custom" in build_config:
                    del build_config["llm_custom"]

                self.insert_in_dict(build_config, "agent_llm", openai_fields)
            elif field_value == "Azure OpenAI":
                for field in openai_fields:
                    if field in build_config:
                        del build_config[field]
                if "llm_custom" in build_config:
                    del build_config["llm_custom"]
                self.insert_in_dict(build_config, "agent_llm", azure_fields)
            elif field_value == "Custom":
                for field in openai_fields:
                    if field in build_config:
                        del build_config[field]
                for field in azure_fields:
                    if field in build_config:
                        del build_config[field]
                llm_custom_fields = HandleInput(
                    name="llm_custom", display_name="Language Model", input_types=["LanguageModel"], required=False
                ).to_dict()
                self.insert_in_dict(build_config, "agent_llm", {"llm_custom": llm_custom_fields})
            build_config["agent_llm"]["value"] = field_value
        return build_config
