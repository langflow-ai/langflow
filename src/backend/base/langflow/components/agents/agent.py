from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.base.models.model_input_constants import ALL_PROVIDER_FIELDS, MODEL_PROVIDERS_DICT
from langflow.components.agents.tool_calling import ToolCallingAgentComponent
from langflow.components.helpers.memory import MemoryComponent
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

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    inputs = [
        DropdownInput(
            name="agent_llm",
            display_name="Model Provider",
            options=[*sorted(MODEL_PROVIDERS_DICT.keys()), "Custom"],
            value="OpenAI",
            real_time_refresh=True,
            refresh_button=True,
            input_types=[],
        ),
        *MODEL_PROVIDERS_DICT["OpenAI"]["inputs"],
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
        if isinstance(self.agent_llm, str):
            try:
                provider_info = MODEL_PROVIDERS_DICT.get(self.agent_llm)
                if provider_info:
                    component_class = provider_info.get("component_class")
                    inputs = provider_info.get("inputs")
                    prefix = provider_info.get("prefix", "")
                    return self._build_llm_model(component_class, inputs, prefix)
            except Exception as e:
                msg = f"Error building {self.agent_llm} language model"
                raise ValueError(msg) from e
        return self.agent_llm

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

    def update_build_config(self, build_config: dotdict, field_value: str, field_name: str | None = None) -> dotdict:
        if field_name == "agent_llm":
            # Define provider configurations as (fields_to_add, fields_to_delete)
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
            default_keys = ["code", "_type", "agent_llm", "tools", "input_value"]
            missing_keys = [key for key in default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)

        return build_config
