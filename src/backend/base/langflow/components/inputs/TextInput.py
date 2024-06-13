from langflow.base.io.text import TextComponent
from langflow.field_typing import Text
from langflow.inputs import StrInput
from langflow.template import Output
from langflow.schema.message import Message


class TextInput(TextComponent):
    display_name = "Text Input"
    description = "Get text inputs from the Playground."
    icon = "type"

    inputs = [
        StrInput(
            name="input_value",
            type=str,
            display_name="Text",
            info="Text to be passed as input.",
            input_types=["Text", "Message"],
        ),
        StrInput(
            name="data_template",
            display_name="Data Template",
            multiline=True,
            info="Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
            advanced=True,
            value="{text}",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text", method="text_response"),
    ]

    def text_response(self) -> Text:
        if isinstance(self.input_value, Message):
            text = self.input_value.text
        else:
            text = self.input_value

        return self.build(input_value=text, data_template=self.data_template)
