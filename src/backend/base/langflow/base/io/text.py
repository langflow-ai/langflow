from typing import Optional, Union

from langflow.field_typing import Text
from langflow.helpers.record import records_to_text
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema.schema import Record


class TextComponent(CustomComponent):
    display_name = "Text Component"
    description = "Used to pass text to the next component."

    def build_config(self):
        return {
            "input_value": {"display_name": "Value", "input_types": ["Record"]},
            "record_template": {"display_name": "Record Template", "multiline": True},
        }

    def build(
        self,
        input_value: Optional[Union[Text, Record]] = "",
        record_template: Optional[str] = "Text: {text}\nData: {data}",
    ) -> Text:
        if isinstance(input_value, Record):
            input_value = records_to_text(template=record_template, records=input_value)
        self.status = input_value
        if not input_value:
            input_value = ""
        return input_value
