from typing import Optional, Union

from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record
from langflow.field_typing import Text

class TextOperatorComponent(CustomComponent):
    display_name = "Text Operator"
    description = "Compares two text inputs based on a specified condition such as equality or inequality, with optional case sensitivity."

    def build_config(self) -> dict:
        return {
            "input_text": {
                "display_name": "Input Text",
                "info": "The primary text input for the operation.",
            },
            "match_text": {
                "display_name": "Match Text",
                "info": "The text input to compare against.",
            },
            "operator": {
                "display_name": "Operator",
                "info": "The operator to apply for comparing the texts.",
                "options": [
                    "equals",
                    "not equals",
                    "contains",
                    "starts with",
                    "ends with",
                    "exists"
                ],
            },
            "case_sensitive": {
                "display_name": "Case Sensitive",
                "info": "If true, the comparison will be case sensitive.",
                "field_type": "bool",
                "default": False,
            },
            "true_output": {
                "display_name": "Output",
                "info": "The output to return or display when the comparison is true.",
                "input_types": ["Text", "Record"],  # Allow both text and record types
            },
        }

    def build(
        self,
        input_text: Text,
        match_text: Text,
        operator: Text,
        case_sensitive: bool = False,
        true_output: Optional[Text] = "",
    ) -> Union[Text, Record]:
        
        if not input_text or not match_text:
            raise ValueError(
                "Both 'input_text' and 'match_text' must be provided and non-empty."
            )

        if not case_sensitive:
            input_text = input_text.lower()
            match_text = match_text.lower()

        result = False
        if operator == "equals":
            result = input_text == match_text
        elif operator == "not equals":
            result = input_text != match_text
        elif operator == "contains":
            result = match_text in input_text
        elif operator == "starts with":
            result = input_text.startswith(match_text)
        elif operator == "ends with":
            result = input_text.endswith(match_text)

        output_record = true_output if true_output else input_text

        if result:
            self.status = output_record
            return output_record
        else:
            self.status = "Comparison failed, stopping execution."
            self.stop()

        return output_record