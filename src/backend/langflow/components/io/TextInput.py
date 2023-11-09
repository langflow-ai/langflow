from typing import Optional, Union
from langflow import CustomComponent
from langflow.field_typing import Text, Data


class TextInput(CustomComponent):
    display_name = "Text Input"
    description = "Used to pass text input to the next component."

    field_config = {
        "code": {
            "show": False,
        },
        "value": {"display_name": "Value"},
    }

    def build(self, value: Optional[str] = "") -> Union[Text, Data]:
        self.repr_value = value
        return value
