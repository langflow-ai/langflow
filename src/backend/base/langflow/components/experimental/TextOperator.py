from langflow.custom import Component
from langflow.field_typing import Text
from langflow.inputs import BoolInput, DropdownInput, StrInput
from langflow.template import Output


class TextOperatorComponent(Component):
    display_name = "Text Operator"
    description = "Compares two text inputs based on a specified condition such as equality or inequality, with optional case sensitivity."
    icon = "equal"

    inputs = [
        StrInput(
            name="input_text",
            display_name="Input Text",
            info="The primary text input for the operation.",
        ),
        StrInput(
            name="match_text",
            display_name="Match Text",
            info="The text input to compare against.",
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="The operator to apply for comparing the texts.",
            value="equals",
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            value=False,
            advanced=True,
        ),
        StrInput(
            name="true_output",
            display_name="True Output",
            info="The output to return or display when the comparison is true. If not passed, defaults to Input Text.",
            advanced=True,
        ),
        StrInput(
            name="false_output",
            display_name="False Output",
            info="The output to return or display when the comparison is false. If not passed, defaults to Input Text.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="True Result", name="true_result", method="true_response"),
        Output(display_name="False Result", name="false_result", method="false_response"),
    ]

    def true_response(self) -> Text:
        self.stop("false_result")
        return self.true_output

    def false_response(self) -> Text:
        self.stop("true_result")
        return self.false_output

    def run(self) -> Text:
        input_text = self.input_text
        match_text = self.match_text
        operator = self.operator
        case_sensitive = self.case_sensitive

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
