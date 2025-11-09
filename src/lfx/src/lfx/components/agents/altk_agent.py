"""ALTK Agent Component that combines pre-tool validation and post-tool processing capabilities."""

from lfx.components.agents.altk_tool_wrappers import PostToolProcessingWrapper, PreToolValidationWrapper

from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT, MODELS_METADATA
from lfx.components.agents.altk_base_agent import ALTKBaseAgentComponent
from lfx.components.helpers.memory import MemoryComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import DropdownInput, IntInput, Output
from lfx.log.logger import logger

from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT, MODELS_METADATA
from lfx.components.agents.altk_base_agent import ALTKBaseAgentComponent
from lfx.components.helpers.memory import MemoryComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import DropdownInput, IntInput, Output
from lfx.log.logger import logger


def set_advanced_true(component_input):
    """Set the advanced flag to True for a component input."""
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]
INPUT_NAMES_TO_BE_OVERRIDDEN = ["agent_llm"]


def get_parent_agent_inputs():
    return [
        input_field
        for input_field in ALTKBaseAgentComponent.inputs
        if input_field.name not in INPUT_NAMES_TO_BE_OVERRIDDEN
    ]


# === Combined ALTK Agent Component ===


class ALTKAgentComponent(ALTKBaseAgentComponent):
    """ALTK Agent with both pre-tool validation and post-tool processing capabilities.

    This agent combines the functionality of both ALTKAgent and AgentReflection components,
    implementing a modular pipeline for tool processing that can be extended with
    additional capabilities in the future.
    """

    display_name: str = "ALTK Agent"
    description: str = (
        "Advanced agent with both pre-tool validation and post-tool processing capabilities."
    )
    documentation: str = "https://docs.langflow.org/agents"
    icon = "zap"
    beta = True
    name = "ALTK Agent"

    memory_inputs = [
        set_advanced_true(component_input)
        for component_input in MemoryComponent().inputs
    ]

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
            options_metadata=[
                MODELS_METADATA[key]
                for key in MODEL_PROVIDERS_LIST
                if key in MODELS_METADATA
            ],
        ),
        *get_parent_agent_inputs(),
        BoolInput(
            name="enable_tool_validation",
            display_name="Tool Validation",
            info="Validates tool calls using SPARC before execution.",
            value=True,
        ),
        BoolInput(
            name="enable_post_tool_reflection",
            display_name="Post Tool JSON Processing",
            info="Processes tool output through JSON analysis.",
            value=True,
        ),
        IntInput(
            name="response_processing_size_threshold",
            display_name="Response Processing Size Threshold",
            value=100,
            info="Tool output is post-processed only if response exceeds this character threshold.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(name="response", display_name="Response", method="message_response"),
    ]

    def configure_tool_pipeline(self) -> None:
        """Configure the tool pipeline with wrappers based on enabled features."""
        wrappers = []

        # Add post-tool processing first (innermost wrapper)
        if self.enable_post_tool_reflection:
            logger.info("Enabling Post-Tool Processing Wrapper!")
            post_processor = PostToolProcessingWrapper(
                response_processing_size_threshold=self.response_processing_size_threshold
            )
            wrappers.append(post_processor)

        # Add pre-tool validation last (outermost wrapper)  
        if self.enable_tool_validation:
            logger.info("Enabling Pre-Tool Validation Wrapper!")
            pre_validator = PreToolValidationWrapper()
            wrappers.append(pre_validator)

        self.pipeline_manager.configure_wrappers(wrappers)

    def update_runnable_instance(self, agent, runnable, tools):
        """Override to add tool specs update for validation wrappers."""
        # Update tool specs for validation wrappers
        for wrapper in self.pipeline_manager.wrappers:
            if isinstance(wrapper, PreToolValidationWrapper) and tools:
                wrapper.tool_specs = (
                    wrapper.convert_langchain_tools_to_sparc_tool_specs_format(tools)
                )
                logger.info(
                    f"Updated tool specs for validation: {len(wrapper.tool_specs)} tools"
                )

        return super().update_runnable_instance(agent, runnable, tools)
