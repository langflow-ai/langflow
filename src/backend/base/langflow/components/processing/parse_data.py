from langflow.custom import Component
from langflow.helpers.data import data_to_text, data_to_text_list
from langflow.io import DataInput, MultilineInput, Output, StrInput
from langflow.schema import Data
from langflow.schema.message import Message


class DataToMessage(Component):
    display_name = "Data to Message"
    description = "Convert Data objects into Message format using customizable templates."
    icon = "message-square"
    name = "DataToMessage"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="One or more Data objects to convert into message format.",
            is_list=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="Template for formatting the message. Use placeholders like {text}, {data}, or any key.",
            value="{text}",
        ),
        StrInput(
            name="separator",
            display_name="Separator",
            info="Character(s) to use when combining multiple messages.",
            value="\n",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Text",
            name="text",
            info="Single Message containing all input Data formatted and combined using the separator",
            method="create_combined_text",
        ),
        Output(
            display_name="Data List",
            name="data_list",
            info="List of individual Messages, each formatted using the template",
            method="create_data_list",
        ),
    ]

    def _prepare_inputs(self) -> tuple[list[Data], str, str]:
        data = self.data if isinstance(self.data, list) else [self.data]
        return data, self.template, self.separator

    def create_combined_text(self) -> Message:
        """Combine all input Data into a single formatted Message."""
        data, template, separator = self._prepare_inputs()
        formatted_text = data_to_text(template, data, separator)
        self.status = formatted_text
        return Message(text=formatted_text)

    def create_data_list(self) -> list[Data]:
        """Create individual formatted Messages for each input Data."""
        data, template, _ = self._prepare_inputs()
        text_list, data_list = data_to_text_list(template, data)

        for item, text in zip(data_list, text_list, strict=True):
            item.set_text(text)

        self.status = data_list
        return data_list
