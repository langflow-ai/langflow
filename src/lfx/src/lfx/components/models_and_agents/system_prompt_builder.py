from lfx.custom import Component
from lfx.io import MultilineInput, Output


class SystemPromptBuilderComponent(Component):
    display_name = "System Prompt Builder"
    description = "Expose instructions from a flow for an agent harness."
    icon = "Text"
    name = "SystemPromptBuilder"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Instructions",
            info="Connect a prompt or enter instructions. Agent placeholders are resolved by the agent.",
            input_types=["Message", "Text"],
            required=True,
        ),
    ]
    outputs = [Output(name="instructions", display_name="Instructions", method="build_instructions")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    def build_instructions(self) -> str:
        if not isinstance(self.input_value, str) or not self.input_value.strip():
            msg = "The instructions flow must produce non-empty text."
            raise ValueError(msg)
        self.status = self.input_value
        return self.input_value
