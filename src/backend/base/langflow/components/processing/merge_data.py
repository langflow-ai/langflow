from enum import Enum
import pandas as pd
from loguru import logger
from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, Output
from langflow.schema import Data, DataFrame

class MergeOperation(str, Enum):
    CONCATENATE = "concatenate"
    APPEND = "append" 
    MERGE = "merge"
    JOIN = "join"

class DataMergerComponent(Component):
    display_name = "Data Merger"
    description = "Combina dados usando operações de merge"
    icon = "merge"

    inputs = [
        DataInput(name="data_inputs", display_name="Data Inputs", info="Dados para combinar", is_list=True),
        DropdownInput(
            name="operation",
            display_name="Merge Operation",
            options=[op.value for op in MergeOperation],
            value=MergeOperation.CONCATENATE.value,
        ),
    ]

    outputs = [Output(display_name="DataFrame", name="merged_data", method="merge_data")]

    def merge_data(self) -> DataFrame:
        if not self.data_inputs or len(self.data_inputs) < 2:
            df = DataFrame(pd.DataFrame())
            self.status = df
            return df

        operation = MergeOperation(self.operation)
        try:
            df = self._process_operation(operation)
            df = DataFrame(df)
            self.status = df
            return df
        except Exception as e:
            logger.error(f"Erro durante operação {operation}: {str(e)}")
            raise

    def _process_operation(self, operation: MergeOperation) -> pd.DataFrame:
        if operation == MergeOperation.CONCATENATE:
            combined_data = {}
            for data_input in self.data_inputs:
                for key, value in data_input.data.items():
                    if key in combined_data:
                        if isinstance(combined_data[key], str) and isinstance(value, str):
                            combined_data[key] = combined_data[key] + "\n" + value
                        else:
                            combined_data[key] = value
                    else:
                        combined_data[key] = value
            return pd.DataFrame([combined_data])

        if operation == MergeOperation.APPEND:
            rows = []
            for data_input in self.data_inputs:
                rows.append(data_input.data)
            return pd.DataFrame(rows)
        
        if operation == MergeOperation.MERGE:
            combined_data = {}
            for idx, data_input in enumerate(self.data_inputs, 1):
                for key, value in data_input.data.items():
                    if key in combined_data and isinstance(value, str):
                        if not isinstance(combined_data[key], list):
                            combined_data[key] = [combined_data[key]]
                        combined_data[key].append(value)
                    else:
                        combined_data[key] = value
            return pd.DataFrame([combined_data])
        
        if operation == MergeOperation.JOIN:
            combined_data = {}
            for idx, data_input in enumerate(self.data_inputs, 1):
                for key, value in data_input.data.items():
                    new_key = f"{key}_doc{idx}" if idx > 1 else key
                    combined_data[new_key] = value
            return pd.DataFrame([combined_data])

        return pd.DataFrame()
