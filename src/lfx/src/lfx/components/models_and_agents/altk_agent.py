"""ALTK Agent Component that combines pre-tool validation and post-tool processing capabilities."""

from lfx.base.agents.altk_base_agent import ALTKBaseAgentComponent
from lfx.base.agents.altk_tool_wrappers import (
    PostToolProcessingWrapper,
    PreToolValidationWrapper,
)
from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT, MODELS_METADATA
from lfx.components.models_and_agents.memory import MemoryComponent
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
    description: str = "Advanced agent with both pre-tool validation and post-tool processing capabilities."
    documentation: str = "https://docs.langflow.org/agents"
    icon = "zap"
    beta = True
    name = "ALTK Agent"

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
        # Get context info (copied from parent)
        user_query = self.get_user_query()
        conversation_context = self.build_conversation_context()

        # Initialize pipeline (this ensures configure_tool_pipeline is called)
        self._initialize_tool_pipeline()

        # Update tool specs for validation wrappers BEFORE processing
        for wrapper in self.pipeline_manager.wrappers:
            if isinstance(wrapper, PreToolValidationWrapper) and tools:
                wrapper.tool_specs = wrapper.convert_langchain_tools_to_sparc_tool_specs_format(tools)

        # Process tools with updated specs
        processed_tools = self.pipeline_manager.process_tools(
            list(tools or []),
            agent=agent,
            user_query=user_query,
            conversation_context=conversation_context,
        )

        runnable.tools = processed_tools
        return runnable

    def __init__(self, **kwargs):
        """Initialize ALTK agent with input normalization for Data.to_lc_message() inconsistencies."""
        super().__init__(**kwargs)

        # If input_value uses Data.to_lc_message(), wrap it to provide consistent content
        if hasattr(self.input_value, "to_lc_message") and callable(self.input_value.to_lc_message):
            self.input_value = self._create_normalized_input_proxy(self.input_value)

    def _create_normalized_input_proxy(self, original_input):
        """Create a proxy that normalizes to_lc_message() content format."""

        class NormalizedInputProxy:
            def __init__(self, original):
                self._original = original

            def __getattr__(self, name):
                if name == "to_lc_message":
                    return self._normalized_to_lc_message
                return getattr(self._original, name)

            def _normalized_to_lc_message(self):
                """Return a message with normalized string content."""
                original_msg = self._original.to_lc_message()

                # If content is in list format, normalize it to string
                if hasattr(original_msg, "content") and isinstance(original_msg.content, list):
                    from langchain_core.messages import AIMessage, HumanMessage

                    from lfx.base.agents.altk_base_agent import (
                        normalize_message_content,
                    )

                    normalized_content = normalize_message_content(original_msg)

                    # Create new message with string content
                    if isinstance(original_msg, HumanMessage):
                        return HumanMessage(content=normalized_content)
                    return AIMessage(content=normalized_content)

                # Return original if already string format
                return original_msg

            def __str__(self):
                return str(self._original)

            def __repr__(self):
                return f"NormalizedInputProxy({self._original!r})"

        return NormalizedInputProxy(original_input)
