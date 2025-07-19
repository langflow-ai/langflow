from lfx.custom.custom_component.component import Component

from langflow.field_typing import Text
from langflow.io import BoolInput, DropdownInput, MessageTextInput, Output


class SelectivePassThroughComponent(Component):
    display_name = "Selective Pass Through"
    description = "Passes the specified value if a specified condition is met."
    icon = "filter"
    name = "SelectivePassThrough"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input Value",
            info="The primary input value to evaluate.",
        ),
        MessageTextInput(
            name="comparison_value",
            display_name="Comparison Value",
            info="The value to compare against the input value.",
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="Condition to evaluate the input value.",
        ),
        MessageTextInput(
            name="value_to_pass",
            display_name="Value to Pass",
            info="The value to pass if the condition is met.",
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Passed Output", name="passed_output", method="pass_through"),
    ]

    def evaluate_condition(
        self, input_value: str, comparison_value: str, operator: str, *, case_sensitive: bool
    ) -> bool:
        if not case_sensitive:
            input_value = input_value.lower()
            comparison_value = comparison_value.lower()

        if operator == "equals":
            return input_value == comparison_value
        if operator == "not equals":
            return input_value != comparison_value
        if operator == "contains":
            return comparison_value in input_value
        if operator == "starts with":
            return input_value.startswith(comparison_value)
        if operator == "ends with":
            return input_value.endswith(comparison_value)
        return False

    def pass_through(self) -> Text:
        input_value = self.input_value
        comparison_value = self.comparison_value
        operator = self.operator
        value_to_pass = self.value_to_pass
        case_sensitive = self.case_sensitive

        if self.evaluate_condition(input_value, comparison_value, operator, case_sensitive=case_sensitive):
            self.status = value_to_pass
            return value_to_pass
        self.status = ""
        return ""
