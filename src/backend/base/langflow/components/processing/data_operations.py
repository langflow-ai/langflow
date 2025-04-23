import ast
from typing import Any

from langflow.custom import Component
from langflow.inputs import DictInput, DropdownInput, MessageTextInput, SortableListInput
from langflow.io import DataInput, Output
from langflow.logging import logger
from langflow.schema import Data
from langflow.utils.component_utils import set_current_fields


class DataOperationsComponent(Component):
    display_name = "Data Operations"
    description = "Perform various operations on a Data object."
    icon = "file-json-2"
    name = "DataOperations"
    default_keys = ["actions", "data"]
    actions_data = {
        "Select Keys": ["select_keys_input", "actions"],
        "Literal Eval": [],
        "Combine": [],
        "Filter Values": ["filter_values", "actions", "operator", "filter_key"],
        "Append or Update Data": ["append_update_data", "actions"],
    }

    inputs = [
        DataInput(name="data", display_name="Data", info="Data object to filter.", required=True, is_list=True),
        SortableListInput(
            name="actions",
            display_name="Actions",
            placeholder="Select action",
            info="List of actions to perform on the data.",
            options=[
                {"name": "Select Keys", "icon": "lasso-select"},
                {"name": "Literal Eval", "icon": "braces"},
                {"name": "Combine", "icon": "merge"},
                {"name": "Filter Values", "icon": "filter"},
                {"name": "Append or Update Data", "icon": "circle-plus"},
            ],
            real_time_refresh=True,
            limit=1,
        ),
        # select keys inputs
        MessageTextInput(
            name="select_keys_input",
            display_name="Select Keys",
            info="List of keys to select from the data.",
            show=False,
            is_list=True,
        ),
        # filter values inputs
        MessageTextInput(
            name="filter_key",
            display_name="Filter Key",
            info="Key to filter by.",
            is_list=True,
            show=False,
        ),
        DropdownInput(
            name="operator",
            display_name="Comparison Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="The operator to apply for comparing the values.",
            value="equals",
            advanced=False,
            show=False,
        ),
        DictInput(
            name="filter_values",
            display_name="Filter Values",
            info="List of values to filter by.",
            show=False,
            is_list=True,
        ),
        # update/ Append data inputs
        DictInput(
            name="append_update_data",
            display_name="Append or Update Data",
            info="Data to append or update the existing data with.",
            show=False,
            value={"key": "value"},
            is_list=True,
        ),
    ]
    outputs = [
        Output(display_name="Data", name="data_output", method="as_data"),
    ]

    def select_keys(self, evaluate: bool | None = None) -> Data:
        data_dict = self.get_data_dict()
        filter_criteria: list[str] = self.select_keys_input

        # Filter the data
        if len(filter_criteria) == 1 and filter_criteria[0] == "data":
            filtered = data_dict["data"]
        else:
            if not all(key in data_dict["data"] for key in filter_criteria):
                msg = f"Select key {self.select_keys} not found in data.Available keys: {data_dict.keys()}"
                raise ValueError(msg)
            filtered = {key: value for key, value in data_dict["data"].items() if key in filter_criteria}

        # Create a new Data object with the filtered data
        if evaluate:
            filtered = self.recursive_eval(filtered)

        filtered_data = Data(**filtered)
        self.status = filtered_data
        return filtered_data

    def recursive_eval(self, data: Any) -> Any:
        """Recursively evaluate string values in a dictionary or list.

        If the value is a string that can be evaluated, it will be evaluated.
        Otherwise, the original value is returned.
        """
        if isinstance(data, dict):
            return {k: self.recursive_eval(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.recursive_eval(item) for item in data]
        if isinstance(data, str):
            try:
                # Only attempt to evaluate strings that look like Python literals
                if (
                    data.strip().startswith(("{", "[", "(", "'", '"'))
                    or data.strip().lower() in ("true", "false", "none")
                    or data.strip().replace(".", "").isdigit()
                ):
                    return ast.literal_eval(data)
                return data
            except (ValueError, SyntaxError, TypeError, MemoryError):  # Catch specific exceptions from ast.literal_eval
                # If evaluation fails for any reason, return the original string
                return data
            else:
                return data
        return data

    def get_data_dict(self) -> dict:
        data = self.data[0] if isinstance(self.data, list) and len(self.data) == 1 else self.data
        return data.model_dump()

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        # if "append_update_data" in build_config and field_name != "append_update_data":
        #     build_config["append_update_data"]["value"] = None
        if field_name == "actions":
            selected_actions = [action["name"] for action in self.actions]
            if "Select Keys" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = False
                logger.info("setting filter fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Select Keys",
                    default_fields=self.default_keys,
                )
            if "Literal Eval" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = False
                logger.info("setting evaluate fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Literal Eval",
                    default_fields=self.default_keys,
                )
            if "Combine" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = True
                logger.info("setting combine fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Combine",
                    default_fields=self.default_keys,
                )
            if "Filter Values" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = True
                logger.info("setting filter values fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Filter Values",
                    default_fields=self.default_keys,
                )
            if "Append or Update Data" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = True

                # build_config = add_fields(
                #     build_config=build_config,
                #     fields=DictInput(
                #         name="append_update_data",
                #         display_name="Append or Update Data",
                #         info="Data to append or update the existing data with.",
                #         show=False,
                #         value={"key": "value"},
                #         is_list=True,
                #     ).to_dict(),
                # )
                logger.info("setting append or update data fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Append or Update Data",
                    default_fields=self.default_keys,
                )
            elif len(selected_actions) == 0:
                logger.info("setting default fields")
                # build_config = delete_fields(build_config=build_config, fields=["append_update_data"])
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action=None,
                    default_fields=self.default_keys,
                )
        return build_config

    def evaluate_data(self) -> Data:
        logger.info("evaluating data")
        return Data(**self.recursive_eval(self.get_data_dict()))

    def combine_data(self, evaluate: bool | None = None) -> Data:
        logger.info("combining data")
        if len(self.data) > 1:
            data_dicts = [data.model_dump()["data"] for data in self.data]
            combined_data = {}
            for data_dict in data_dicts:
                for key, value in data_dict.items():
                    if key not in combined_data:
                        combined_data[key] = value
                    elif isinstance(combined_data[key], list):
                        if isinstance(value, list):
                            combined_data[key].extend(value)
                        else:
                            combined_data[key].append(value)
                    # If current value is not a list, convert it to list and add new value
                    else:
                        combined_data[key] = (
                            [combined_data[key], value] if not isinstance(value, list) else [combined_data[key], *value]
                        )
            if evaluate:
                combined_data = self.recursive_eval(combined_data)
            return Data(**combined_data)

        # If there's only one data object, return it as is
        return self.data[0] if self.data else None

    def compare_values(self, item_value: Any, filter_value: str, operator: str) -> bool:
        if operator == "equals":
            return str(item_value) == str(filter_value)
        if operator == "not equals":
            return str(item_value) != str(filter_value)
        if operator == "contains":
            return str(filter_value) in str(item_value)
        if operator == "starts with":
            return str(item_value).startswith(str(filter_value))
        if operator == "ends with":
            return str(item_value).endswith(str(filter_value))
        return False

    def filter_data(
        self, input_data: list[dict[str, Any]], filter_key: str, filter_value: str, operator: str
    ) -> list[Data]:
        # Validate inputs
        if not input_data:
            self.status = "Input data is empty."
            return []

        if not filter_key or not filter_value:
            self.status = "Filter key or value is missing."
            return input_data

        # Filter the data
        filtered_data = []
        for item in input_data:
            if isinstance(item, dict) and filter_key in item:
                if self.compare_values(item[filter_key], filter_value, operator):
                    filtered_data.append(item)
            else:
                self.status = f"Warning: Some items don't have the key '{filter_key}' or are not dictionaries."

        return filtered_data

    def multi_filter_data(self) -> list[Data]:
        data_filtered = self.get_data_dict()
        if "data" in data_filtered:
            data_filtered = data_filtered["data"]
        for filter_key in self.filter_key:
            if filter_key not in data_filtered:
                msg = f"Filter key {filter_key} not found in data.Available keys: {data_filtered.keys()}"
                raise ValueError(msg)
            if isinstance(data_filtered[filter_key], list):
                for filter_data in self.filter_values:
                    # get key and value from
                    data_filtered[filter_key] = self.filter_data(
                        input_data=data_filtered[filter_key],
                        filter_key=filter_data,
                        filter_value=self.filter_values.get(filter_data, None),
                        operator=self.operator,
                    )
            else:
                msg = f"Filter key {filter_key} is not a list."
                raise TypeError(msg)
        return Data(**data_filtered)

    def append_update(self) -> Data:
        data_filtered = self.get_data_dict()
        if "data" in data_filtered:
            data_filtered = data_filtered["data"]
        for key, value in self.append_update_data.items():
            data_filtered[key] = value
        return Data(**data_filtered)

    def data_is_list(self) -> bool:
        return len(self.data) > 1

    def data_list_exception(self, operation: str):
        msg = f"{operation} operation is not supported for multiple data objects."
        raise ValueError(msg)

    def operation_exception(self, operations: list[str]):
        msg = f"{operations} operation is not supported in combination with each other"
        raise ValueError(msg)

    def as_data(self) -> Data:
        selected_actions = [action["name"] for action in self.actions]
        logger.info("selected_actions", selected_actions)
        if "Select Keys" in selected_actions and len(selected_actions) == 1:
            if self.data_is_list():
                self.data_list_exception("Select Keys")
            return self.select_keys()
        if "Literal Eval" in selected_actions and len(selected_actions) == 1:
            if self.data_is_list():
                self.data_list_exception("Literal Eval")
            return self.evaluate_data()
        # if "Select Keys" in selected_actions and "Literal Eval" in selected_actions:
        #     if self.data_is_list():
        #         self.data_list_exception("Filter and Evaluate")
        #     return self.select_keys(evaluate=True)
        # if "Literal Eval" in selected_actions and "Combine" in selected_actions:
        #     return self.combine_data(evaluate=True)
        # if "Select Keys" in selected_actions and "Combine" in selected_actions:
        #     self.operation_exception(["Select Keys", "Combine"])
        if "Combine" in selected_actions and len(selected_actions) == 1:
            return self.combine_data()
        if "Filter Values" in selected_actions and len(selected_actions) == 1:
            if self.data_is_list():
                self.data_list_exception("Filter Values")
            return self.multi_filter_data()
        if "Append or Update Data" in selected_actions and len(selected_actions) == 1:
            if self.data_is_list():
                self.data_list_exception("Append or Update Data")
            return self.append_update()
        return None
