from langflow.custom import Component
from langflow.helpers.data import data_to_text, data_to_text_list
from langflow.io import DataInput, MultilineInput, Output, StrInput
from langflow.schema import Data
from langflow.schema.message import Message


class ParseDataComponent(Component):
    """Convert Data objects into Message format."""

    display_name = "Data to Message"
    description = "Convert data objects into message format for easier processing."
    icon = "MessageSquare"
    name = "parse_data"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="Data object(s) to convert into message format.",
            is_list=True,
        ),
        StrInput(
            name="field",
            display_name="Field",
            info="Field to extract from the data object. Leave empty to use all fields.",
            required=False,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="Template to use for formatting the data. Use {field} to reference fields.",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Message", name="message", method="parse_data"),
    ]

    def parse_data(self) -> Message:
        """Convert Data objects into Message format."""
        if not self.data:
            return Message(content="")

        if self.template:
            text = data_to_text_list(self.data, self.template)
        elif self.field:
            text = data_to_text_list(self.data, "{" + self.field + "}")
        else:
            text = data_to_text(self.data)

        return Message(content=text)
