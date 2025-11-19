from langflow.base.io.text import TextComponent
from langflow.io import MultilineInput, Output
from langflow.schema.message import Message


class FileInputComponent(TextComponent):
    display_name = "File Input"
    description = "Get user file path inputs."
    documentation: str = "https://docs.langflow.org/components-io#file-path-input"
    icon = "type"
    name = "FilePathInput"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="File Path",
            info="File path to be passed as input.",    
        ),
    ]
    outputs = [
        Output(display_name="Output Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Message:
        return Message(
            text=self.input_value,
        )
