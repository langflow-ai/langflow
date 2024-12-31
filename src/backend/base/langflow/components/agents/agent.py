from langchain_core.tools import StructuredTool

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.base.models.model_input_constants import (
    ALL_PROVIDER_FIELDS,
    MODEL_PROVIDERS_DICT,
)
from langflow.base.models.model_utils import get_model_name
from langflow.components.helpers import CurrentDateComponent
from langflow.components.helpers.memory import MemoryComponent
from langflow.components.langchain_utilities.tool_calling import (
    ToolCallingAgentComponent,
)
from langflow.custom.utils import update_component_build_config
from langflow.io import BoolInput, DropdownInput, MultilineInput, Output
from langflow.logging import logger
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message


def set_advanced_true(component_input):
    component_input.advanced = True
    return component_input


class AgentComponent(ToolCallingAgentComponent):
    display_name: str = "Agent"
    description: str = "Define the agent's instructions, then enter a task to complete using tools."
    icon = "bot"
    beta = False
    name = "Agent"

    memory_inputs = [set_advanced_true(component_input) for component_input in MemoryComponent().inputs]

    inputs = [
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
        *memory_inputs,
        BoolInput(
            name="add_current_date_tool",
            display_name="Current Date",
            advanced=True,
            info="If true, will add a tool to the agent that returns the current date.",
            value=True,
        ),
    ]
    outputs = [Output(name="response", display_name="Response", method="message_response")]

    async def message_response(self) -> Message:
        try:
            llm_model, display_name = self.get_llm()
            if llm_model is None:
                msg = "No language model selected"
                raise ValueError(msg)
            self.model_name = get_model_name(llm_model, display_name=display_name)
        except Exception as e:
            # Log the error for debugging purposes
            logger.error(f"Error retrieving language model: {e}")
            raise

        try:
            self.chat_history = await self.get_memory_data()
        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}")
            raise

        if self.add_current_date_tool:
            try:
                if not isinstance(self.tools, list):  # type: ignore[has-type]
                    self.tools = []
                # Convert CurrentDateComponent to a StructuredTool
                current_date_tool = CurrentDateComponent().to_toolkit()[0]
                if isinstance(current_date_tool, StructuredTool):
                    self.tools.append(current_date_tool)
                else:
                    msg = "CurrentDateComponent must be converted to a StructuredTool"
                    raise TypeError(msg)
            except Exception as e:
                logger.error(f"Error adding current date tool: {e}")
                raise

        if not self.tools:
            msg = "Tools are required to run the agent."
            logger.error(msg)
            raise ValueError(msg)

        try:
            self.set(
                llm=llm_model,
                tools=self.tools,
                chat_history=self.chat_history,
                input_value=self.input_value,
                system_prompt=self.system_prompt,
            )
            agent = self.create_agent_runnable()
        except Exception as e:
            logger.error(f"Error setting up the agent: {e}")
            raise

        return await self.run_agent(agent)

    async def get_memory_data(self):
        memory_kwargs = {
            component_input.name: getattr(self, f"{component_input.name}") for component_input in self.memory_inputs
        }

        return await MemoryComponent().set(**memory_kwargs).retrieve_messages()

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
