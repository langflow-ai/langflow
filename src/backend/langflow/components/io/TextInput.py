from typing import Optional, Union
from langflow import CustomComponent
from langflow.field_typing import Text, Data


class TextInput(CustomComponent):
    display_name = "Text Input"
    description = "Used to pass text input to the next component."

    field_config = {
        "code": {
            "show": False,
        }
    }

    def build(self, message: Optional[str] = "") -> Union[Text, Data]:
        self.repr_value = message
        return message
