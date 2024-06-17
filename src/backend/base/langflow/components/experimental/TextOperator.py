from langflow.custom import Component
from langflow.field_typing import Text
from langflow.inputs import BoolInput, DropdownInput, TextInput
from langflow.template import Output


class TextOperatorComponent(Component):
    display_name = "Text Operator"
    description = "Compares two text inputs based on a specified condition such as equality or inequality, with optional case sensitivity."
    icon = "equal"

    inputs = [
        TextInput(
            name="input_text",
            display_name="Input Text",
            info="The primary text input for the operation.",
        ),
        TextInput(
            name="match_text",
            display_name="Match Text",
            info="The text input to compare against.",
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="The operator to apply for comparing the texts.",
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            value=False,
            advanced=True,
        ),
        TextInput(
            name="true_output",
            display_name="True Output",
            info="The output to return or display when the comparison is true.",
            advanced=True,
        ),
        TextInput(
            name="false_output",
            display_name="False Output",
            info="The output to return or display when the comparison is false.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="True Result", name="true_result", method="true_response"),
        Output(display_name="False Result", name="false_result", method="false_response"),
    ]

    def evaluate_condition(self, input_text: str, match_text: str, operator: str, case_sensitive: bool) -> bool:
        if not case_sensitive:
            input_text = input_text.lower()
            match_text = match_text.lower()

        if operator == "equals":
            return input_text == match_text
        elif operator == "not equals":
            return input_text != match_text
        elif operator == "contains":
            return match_text in input_text
        elif operator == "starts with":
            return input_text.startswith(match_text)
        elif operator == "ends with":
            return input_text.endswith(match_text)
        return False

    def true_response(self) -> Text:
        result = self.evaluate_condition(self.input_text, self.match_text, self.operator, self.case_sensitive)
        if result:
            self.stop("false_result")
            response = self.true_output if self.true_output else self.input_text
            self.status = response
            return response
        else:
            self.stop("true_result")
            return ""

    def false_response(self) -> Text:
        result = self.evaluate_condition(self.input_text, self.match_text, self.operator, self.case_sensitive)
        if not result:
            self.stop("true_result")
            response = self.false_output if self.false_output else self.input_text
            self.status = response
            return response
        else:
            self.stop("false_result")
            return ""
