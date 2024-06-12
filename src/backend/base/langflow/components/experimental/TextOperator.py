from typing import Union

from langflow.custom import Component
from langflow.field_typing import Text
from langflow.schema import Data
from langflow.template import Input, Output


class TextOperatorComponent(Component):
    display_name = "Text Operator"
    description = "Compares two text inputs based on a specified condition such as equality or inequality, with optional case sensitivity."

    inputs = [
        Input(name="input_text", type=str, display_name="Input Text", info="The primary text input for the operation."),
        Input(name="match_text", type=str, display_name="Match Text", info="The text input to compare against."),
        Input(
            name="operator",
            type=str,
            display_name="Operator",
            info="The operator to apply for comparing the texts.",
            options=["equals", "not equals", "contains", "starts with", "ends with", "exists"],
        ),
        Input(
            name="case_sensitive",
            type=bool,
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            default=False,
        ),
        Input(
            name="true_output",
            type=Union[str, Data],
            display_name="True Output",
            info="The output to return or display when the comparison is true.",
            input_types=["Text", "Data"],
        ),
        Input(
            name="false_output",
            type=Union[str, Data],
            display_name="False Output",
            info="The output to return or display when the comparison is false.",
            input_types=["Text", "Data"],
        ),
    ]
    outputs = [
        Output(display_name="True Result", name="true_result", method="result_response"),
        Output(display_name="False Result", name="false_result", method="result_response"),
    ]

    def true_response(self) -> Union[Text, Data]:
        self.stop("False Result")
        return self.true_output if self.true_output else self.input_text

    def false_response(self) -> Union[Text, Data]:
        self.stop("True Result")
        return self.false_output if self.false_output else self.input_text

    def result_response(self) -> Union[Text, Data]:
        input_text = self.input_text
        match_text = self.match_text
        operator = self.operator
        case_sensitive = self.case_sensitive

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

        if result:
            response = self.true_response()
            self.status = response
            return response
        else:
            response = self.false_response()
            self.status = response
            return response
