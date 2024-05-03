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
                "options": ["equals", "not equals", "contains", "starts with", "ends with"],
            },
            "case_sensitive": {
                "display_name": "Case Sensitive",
                "info": "If true, the comparison will be case sensitive.",
                "field_type": "bool",
                "default": False,
            }
        }

    def build(self, input_text: Text, match_text: Text, operator: Text, case_sensitive: bool = False) -> Text:
        if not input_text or not match_text:
            raise ValueError("Both 'input_text' and 'match_text' must be provided and non-empty.")

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

        if not result:
            self.stop()
        self.status = f"{result} \n\n {input_text}"
        return input_text
