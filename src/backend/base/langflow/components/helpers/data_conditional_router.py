from typing import Any

from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, MessageTextInput, Output
from langflow.schema import Data, dotdict


class DataConditionalRouterComponent(Component):
    display_name = "Data Conditional Router"
    description = "Route Data object(s) based on a condition applied to a specified key, including boolean validation."
    icon = "split"
    beta = True
    name = "DataConditionalRouter"

    inputs = [
        DataInput(
            name="data_input",
            display_name="Data Input",
            info="The Data object or list of Data objects to process",
            is_list=True,
        ),
        MessageTextInput(
            name="key_name",
            display_name="Key Name",
            info="The name of the key in the Data object(s) to check",
        ),
        DropdownInput(
            name="operator",
            display_name="Comparison Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with", "boolean validator"],
            info="The operator to apply for comparing the values. 'boolean validator' treats the value as a boolean.",
            value="equals",
        ),
        MessageTextInput(
            name="compare_value",
            display_name="Compare Value",
            info="The value to compare against (not used for boolean validator)",
        ),
    ]

    outputs = [
        Output(display_name="True Output", name="true_output", method="process_data"),
        Output(display_name="False Output", name="false_output", method="process_data"),
    ]

    def compare_values(self, item_value: str, compare_value: str, operator: str) -> bool:
        if operator == "equals":
            return item_value == compare_value
        if operator == "not equals":
            return item_value != compare_value
        if operator == "contains":
            return compare_value in item_value
        if operator == "starts with":
            return item_value.startswith(compare_value)
        if operator == "ends with":
            return item_value.endswith(compare_value)
        if operator == "boolean validator":
            return self.parse_boolean(item_value)
        return False

    def parse_boolean(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "y", "on"}
        return bool(value)

    def validate_input(self, data_item: Data) -> bool:
        if not isinstance(data_item, Data):
            self.status = "Input is not a Data object"
            return False
        if self.key_name not in data_item.data:
            self.status = f"Key '{self.key_name}' not found in Data"
            return False
        return True

    def process_data(self) -> Data | list[Data]:
        if isinstance(self.data_input, list):
            true_output = []
            false_output = []
            for item in self.data_input:
                if self.validate_input(item):
                    result = self.process_single_data(item)
                    if result:
                        true_output.append(item)
                    else:
                        false_output.append(item)
            self.stop("false_output" if true_output else "true_output")
            return true_output or false_output
        if not self.validate_input(self.data_input):
            return Data(data={"error": self.status})
        result = self.process_single_data(self.data_input)
        self.stop("false_output" if result else "true_output")
        return self.data_input

    def process_single_data(self, data_item: Data) -> bool:
        item_value = data_item.data[self.key_name]
        operator = self.operator

        if operator == "boolean validator":
            condition_met = self.parse_boolean(item_value)
            condition_description = f"Boolean validation of '{self.key_name}'"
        else:
            compare_value = self.compare_value
            condition_met = self.compare_values(str(item_value), compare_value, operator)
            condition_description = f"{self.key_name} {operator} {compare_value}"

        if condition_met:
            self.status = f"Condition met: {condition_description}"
            return True
        self.status = f"Condition not met: {condition_description}"
        return False

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "operator":
            if field_value == "boolean validator":
                build_config["compare_value"]["show"] = False
                build_config["compare_value"]["advanced"] = True
                build_config["compare_value"]["value"] = None
            else:
                build_config["compare_value"]["show"] = True
                build_config["compare_value"]["advanced"] = False

        return build_config
