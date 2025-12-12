from lfx.base.io.text import TextComponent
from lfx.io import BoolInput, MultilineInput, Output
from lfx.schema.message import Message


class TextInputComponent(TextComponent):
    display_name = "Text Input"
    description = "Get user text inputs."
    documentation: str = "https://docs.langflow.org/text-input-and-output"
    icon = "type"
    name = "TextInput"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as input.",
        ),
        MultilineInput(
            name="mcp_description", display_name="MCP Description", info="Description to MCP Client.", advanced=True
        ),
        BoolInput(name="mcp_required", display_name="MCP Required", info="Required by the MCP Server.", advanced=True),
    ]
    outputs = [
        Output(display_name="Output Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Message:
        return Message(
            text=self.input_value,
        )
