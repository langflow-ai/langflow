"""Compatibility component for ALTK nodes saved before Langflow 1.13.0."""

from lfx.base.agents.altk_base_agent import ALTKBaseAgentComponent
from lfx.base.models.model_input_constants import MODEL_PROVIDERS_DICT, MODELS_METADATA
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.inputs.inputs import BoolInput
from lfx.io import DropdownInput, IntInput, Output


def set_advanced_true(component_input):
    """Set the advanced flag to True for a component input."""
    component_input.advanced = True
    return component_input


MODEL_PROVIDERS_LIST = ["Anthropic", "OpenAI"]
INPUT_NAMES_TO_BE_OVERRIDDEN = ["agent_llm"]
VERBOSE_INPUT_INFO = (
    "Legacy toggle. The '> Entering new ... chain' / '> Finished chain.' "
    "markers it used to print to stdout are now gated on the "
    "LANGCHAIN_VERBOSE environment variable (off by default); set "
    "LANGCHAIN_VERBOSE=true to emit them. Toggling this input on its own no "
    "longer attaches LangChain's stdout handler. Agent steps remain visible "
    "in the UI regardless of this setting."
)


def get_parent_agent_inputs():
    """Retain the historical configuration fields so saved nodes remain inspectable."""
    overrides = {
        "handle_parsing_errors": BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
            info="Should the Agent fix errors when reading user input for better processing?",
        ),
        "max_iterations": IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=15,
            advanced=True,
            info="The maximum number of attempts the agent can make to complete its task before it stops.",
        ),
    }
    parent_inputs = [
        overrides.get(input_field.name, input_field)
        for input_field in ALTKBaseAgentComponent.inputs
        if input_field.name not in INPUT_NAMES_TO_BE_OVERRIDDEN
    ]
    # Keep the historical verbose field even though the parent no longer has it.
    rebuilt: list = []
    for input_field in parent_inputs:
        rebuilt.append(input_field)
        if input_field.name == "handle_parsing_errors":
            rebuilt.append(
                BoolInput(
                    name="verbose",
                    display_name="Verbose",
                    value=True,
                    advanced=True,
                    info=VERBOSE_INPUT_INFO,
                )
            )
    return rebuilt


# === Combined ALTK Agent Component ===


class ALTKAgentComponent(ALTKBaseAgentComponent):
    """Retired node retained for saved-flow compatibility and migration guidance."""

    display_name: str = "ALTK Agent"
    description: str = "ALTK was retired in Langflow 1.13.0. Replace this node with the Agent component."
    documentation: str = "https://docs.langflow.org/bundles-altk"
    icon = "zap"
    beta = True
    name = "ALTK Agent"
    legacy = True
    replacement = ["models_and_agents.Agent"]

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
