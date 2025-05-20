from enum import Enum
from typing import cast

from loguru import logger

from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, Output
from langflow.schema import DataFrame


class DataOperation(str, Enum):
    CONCATENATE = "Concatenate"
    APPEND = "Append"
    MERGE = "Merge"
    JOIN = "Join"


class MergeDataComponent(Component):
    display_name = "Combine Data"
    description = "Combines data using different operations"
    icon = "merge"
    MIN_INPUTS_REQUIRED = 2
    legacy = True

    inputs = [
        DataInput(name="data_inputs", display_name="Data Inputs", info="Data to combine", is_list=True, required=True),
        DropdownInput(
            name="operation",
            display_name="Operation Type",
            options=[op.value for op in DataOperation],
            value=DataOperation.CONCATENATE.value,
        ),
    ]
    outputs = [Output(display_name="DataFrame", name="combined_data", method="combine_data")]

    def combine_data(self) -> DataFrame:
        if not self.data_inputs or len(self.data_inputs) < self.MIN_INPUTS_REQUIRED:
            empty_dataframe = DataFrame()
            self.status = empty_dataframe
            return empty_dataframe

        operation = DataOperation(self.operation)
        try:
            combined_dataframe = self._process_operation(operation)
            self.status = combined_dataframe
        except Exception as e:
            logger.error(f"Error during operation {operation}: {e!s}")
            raise
        else:
            return combined_dataframe

    def _process_operation(self, operation: DataOperation) -> DataFrame:
        if operation == DataOperation.CONCATENATE:
            combined_data: dict[str, str | object] = {}
            for data_input in self.data_inputs:
                for key, value in data_input.data.items():
                    if key in combined_data:
                        if isinstance(combined_data[key], str) and isinstance(value, str):
                            combined_data[key] = f"{combined_data[key]}\n{value}"
                        else:
                            combined_data[key] = value
                    else:
                        combined_data[key] = value
            return DataFrame([combined_data])

        if operation == DataOperation.APPEND:
            rows = [data_input.data for data_input in self.data_inputs]
            return DataFrame(rows)

        if operation == DataOperation.MERGE:
            result_data: dict[str, str | list[str] | object] = {}
            for data_input in self.data_inputs:
                for key, value in data_input.data.items():
                    if key in result_data and isinstance(value, str):
                        if isinstance(result_data[key], list):
                            cast("list[str]", result_data[key]).append(value)
                        else:
                            result_data[key] = [result_data[key], value]
                    else:
                        result_data[key] = value
            return DataFrame([result_data])

        if operation == DataOperation.JOIN:
            combined_data = {}
            for idx, data_input in enumerate(self.data_inputs, 1):
                for key, value in data_input.data.items():
                    new_key = f"{key}_doc{idx}" if idx > 1 else key
                    combined_data[new_key] = value
            return DataFrame([combined_data])

        return DataFrame()
