from langflow.custom import Component
from langflow.io import DataInput, MessageTextInput, DropdownInput, Output
from langflow.schema import Data, dotdict

class DataConditionalRouterComponent(Component):
    display_name = "Data Conditional Router"
    description = "Route a Data object based on a condition applied to a specified key, including boolean validation."
    icon = "split"
    beta = True
    name = "DataConditionalRouter"

    inputs = [
        DataInput(
            name="data_input",
            display_name="Data Input",
            info="The Data object to process",
        ),
        MessageTextInput(
            name="key_name",
            display_name="Key Name",
            info="The name of the key in the Data object to check",
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
        elif operator == "not equals":
            return item_value != compare_value
        elif operator == "contains":
            return compare_value in item_value
        elif operator == "starts with":
            return item_value.startswith(compare_value)
        elif operator == "ends with":
            return item_value.endswith(compare_value)
        elif operator == "boolean validator":
            return self.parse_boolean(item_value)
        return False

    def parse_boolean(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'y', 'on']
        return bool(value)

    def validate_input(self):
        if not isinstance(self.data_input, Data):
            self.status = "Input is not a Data object"
            return False
        if self.key_name not in self.data_input.data:
            self.status = f"Key '{self.key_name}' not found in Data"
            return False
        return True

    def process_data(self) -> Data:
        if not self.validate_input():
            return Data(data={"error": self.status})

        item_value = self.data_input.data[self.key_name]
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
            self.stop("false_output")
            return self.data_input
        else:
            self.status = f"Condition not met: {condition_description}"
            self.stop("true_output")
            return self.data_input

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
