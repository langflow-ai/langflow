from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class CombineTextComponent(Component):
    display_name = "Combine Text"
    description = "Concatenate two text sources into a single text chunk using a specified delimiter."
    icon = "merge"
    name = "CombineText"

    inputs = [
        MessageTextInput(
            name="text1",
            display_name="First Text",
            info="The first text input to concatenate.",
        ),
        MessageTextInput(
            name="text2",
            display_name="Second Text",
            info="The second text input to concatenate.",
        ),
        MessageTextInput(
            name="delimiter",
            display_name="Delimiter",
            info="A string used to separate the two text inputs. Defaults to a whitespace.",
            value=" ",
        ),
    ]

    outputs = [
        Output(display_name="Combined Text", name="combined_text", method="combine_texts"),
    ]

    def combine_texts(self) -> Message:
        combined = self.delimiter.join([self.text1, self.text2])
        self.status = combined
        return Message(text=combined)
