from typing import Optional

from langflow.custom import Component
from langflow.field_typing import Text
from langflow.helpers.data import data_to_text
from langflow.schema import Data


class TextComponent(Component):
    display_name = "Text Component"
    description = "Used to pass text to the next component."

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Value",
                "input_types": ["Text", "Data"],
                "info": "Text or Data to be passed.",
            },
            "data_template": {
                "display_name": "Data Template",
                "multiline": True,
                "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Optional[Text] = "",
        data_template: Optional[str] = "{text}",
    ) -> Text:
        if isinstance(input_value, Data):
            if data_template == "":
                # it should be dynamically set to the Data's .text_key value
                # meaning, if text_key = "bacon", then data_template = "{bacon}"
                data_template = "{" + input_value.text_key + "}"
            input_value = data_to_text(template=data_template, data=input_value)
        elif not input_value:
            input_value = ""
        self.status = input_value
        if not input_value:
            input_value = ""
        return input_value
