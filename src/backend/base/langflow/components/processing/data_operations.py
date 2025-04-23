from typing import Any
import ast

from langflow.custom import Component
from langflow.inputs import DropdownInput, SortableListInput
from langflow.io import DataInput, Output
from langflow.schema import Data
from langflow.utils.component_utils import set_current_fields, update_fields


class DataOperationsComponent(Component):
    display_name = "Data Operations"
    description = "Perform various operations on a Data object."
    icon = "file-json-2"
    name = "DataOperations"
    default_keys = ["actions", "data"]
    actions_data = {"Filter": ["filter_keys", "actions"], "Evaluate": [], "Combine": []}

    inputs = [
        DataInput(name="data", display_name="Data", info="Data object to filter.", required=True, is_list=True),
        SortableListInput(
            name="actions",
            display_name="Actions",
            placeholder="Select action",
            info="List of actions to perform on the data.",
            options=[
                {"name": "Filter", "value": "filter", "icon": "filter"},
                {"name": "Combine", "value": "combine", "icon": "merge"},
                {"name": "Evaluate", "value": "evaluate", "icon": "braces"},
            ],
            real_time_refresh=True,
            limit=1,
        ),
        # filter inputs
        DropdownInput(
            name="filter_keys",
            display_name="Filter Keys",
            info="List of keys to filter by.",
            show=False,
            options=["data", "text_key", "source", "result", "text"],
            combobox=True,
        ),
    ]
    outputs = [
        Output(display_name="Data", name="data_output", method="as_data"),
    ]

    def filter_data(self, evaluate: bool | None = None) -> Data:
        print("filtering data")
        data_dict = self.get_data_dict()

        filter_criteria: list[str] = [self.filter_keys]
        # print("filter_criteria", filter_criteria)
        # print("data_dict",data_dict.keys())
        # print("data_dict",data_dict)

        # Filter the data
        if self.filter_keys == "data":
            filtered = data_dict["data"]
        else:
            if self.filter_keys not in data_dict["data"]:
                print("filter_keys", self.filter_keys)
                print("data_dict", data_dict.keys())
                msg = f"Filter key {self.filter_keys} not found in data.Available keys: {data_dict.keys()}"
                raise ValueError(msg)
            filtered = {key: value for key, value in data_dict["data"].items() if key in filter_criteria}
        print("filtered_keys", filtered.keys())

        # Create a new Data object with the filtered data
        if evaluate:
            print("evaluating data with filter")
            filtered = self.recursive_eval(filtered)
        # print("filtered", filtered)

        filtered_data = Data(**filtered)
        self.status = filtered_data
        # print("filtered_data", filtered_data)
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
            except Exception:  # Catch all exceptions including ValueError
                # If evaluation fails for any reason, return the original string
                return data
        return data

    def get_data_dict(self) -> dict:
        data = self.data[0] if isinstance(self.data, list) and len(self.data) == 1 else self.data
        return data.model_dump()

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "actions":
            # options = [{"name": key, "value": key} for key in self.get_data_dict()]
            # print(f"options: {options}")
            # update_fields(build_config=build_config, fields={"filter_keys": {"options": options}})
            selected_actions = [action["name"] for action in self.actions]
            if "Filter" in selected_actions:
                build_config["data"]["is_list"] = False
                print("setting filter fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Filter",
                    default_fields=self.default_keys,
                )
            if "Evaluate" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = False
                print("setting evaluate fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Evaluate",
                    default_fields=self.default_keys,
                )
            if "Combine" in selected_actions and len(selected_actions) == 1:
                build_config["data"]["is_list"] = True
                print("setting combine fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action="Combine",
                    default_fields=self.default_keys,
                )
            elif len(selected_actions) == 0:
                print("setting default fields")
                build_config = set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action=None,
                    default_fields=self.default_keys,
                )
        return build_config

    def evaluate_data(self) -> Data:
        print("evaluating data")
        return Data(**self.recursive_eval(self.get_data_dict()))

    def combine_data(self, evaluate: bool | None = None) -> Data:
        print("combining data")
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
            return Data(data=combined_data)

        # If there's only one data object, return it as is
        return self.data[0] if self.data else None

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
        if "Filter" in selected_actions and len(selected_actions) == 1:
            if self.data_is_list():
                self.data_list_exception("Filter")
            return self.filter_data()
        if "Evaluate" in selected_actions and len(selected_actions) == 1:
            if self.data_is_list():
                self.data_list_exception("Evaluate")
            return self.evaluate_data()
        if "Filter" in selected_actions and "Evaluate" in selected_actions:
            if self.data_is_list():
                self.data_list_exception("Filter and Evaluate")
            return self.filter_data(evaluate=True)
        if "Evaluate" in selected_actions and "Combine" in selected_actions:
            return self.combine_data(evaluate=True)
        if "Filter" in selected_actions and "Combine" in selected_actions:
            self.operation_exception(["Filter", "Combine"])
        if "Combine" in selected_actions and len(selected_actions) == 1:
            return self.combine_data()
        return None
