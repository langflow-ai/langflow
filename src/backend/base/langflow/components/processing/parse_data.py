from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.io import DataInput, MultilineInput, Output, StrInput
from langflow.schema.message import Message


class DataToMessageComponent(Component):
    display_name = "Data to Message"
    description = "Converts structured data into a formatted message string."
    icon = "braces"
    name = "DataToMessage"

    inputs = [
        DataInput(
            name="data", 
            display_name="Input Data", 
            info="The structured data to be converted into a message."
        ),
        MultilineInput(
            name="template",
            display_name="Message Template",
            info="The template used to format the data into a message. "
                 "Use {text}, {data}, or any key from the input data structure.",
            value="{text}",
        ),
        StrInput(
            name="separator", 
            display_name="Line Separator", 
            advanced=True, 
            value="\n",
            info="The string used to separate lines in the output message."
        ),
    ]

    outputs = [
        Output(display_name="Formatted Message", name="message", method="convert_data_to_message"),
    ]

    def convert_data_to_message(self) -> Message:
        input_data = self.data if isinstance(self.data, list) else [self.data]
        template = self.template

        formatted_message = data_to_text(template, input_data, sep=self.separator)
        self.status = formatted_message
        return Message(text=formatted_message)
