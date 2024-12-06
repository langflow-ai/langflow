from enum import Enum
import pandas as pd
from loguru import logger
from typing import Optional

from langflow.custom import Component
from langflow.io import DataInput, DropdownInput, Output
from langflow.schema import Data, DataFrame


class MergeOperation(str, Enum):
    """Supported merge operations for combining data."""
    CONCATENATE = "concatenate"  # Combines text values with newlines
    APPEND = "append"  # Adds rows vertically
    MERGE = "merge"  # Combines values into lists
    JOIN = "join"  # Adds columns with suffixes


class DataMergerComponent(Component):
    """Component for merging multiple Data objects using various operations.
    
    This component supports different merge strategies:
    - Concatenate: Combines text values with newlines
    - Append: Adds data as new rows
    - Merge: Combines values into lists
    - Join: Adds columns with suffixes for disambiguation
    """

    display_name = "Data Merger"
    description = "Combines data using standard merge operations (concatenate, append, merge, join)"
    icon = "merge"

    inputs = [
        DataInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="List of Data objects to combine. Minimum 2 inputs required for merging.",
            is_list=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Merge Operation",
            info=(
                "Select how to combine the data:\n"
                "- Concatenate: Combines text values with newlines\n"
                "- Append: Adds data as new rows\n"
                "- Merge: Combines values into lists\n"
                "- Join: Adds columns with suffixes"
            ),
            options=[op.value for op in MergeOperation],
            value=MergeOperation.CONCATENATE.value,
        ),
    ]

    outputs = [
        Output(
            display_name="DataFrame",
            name="merged_data",
            method="merge_data",
        )
    ]

    def merge_data(self) -> DataFrame:
        """Merges input data using the selected operation.

        Returns:
            DataFrame: Result of merging the input data.
            Empty DataFrame if insufficient inputs.
        """
        if not self.data_inputs or len(self.data_inputs) < 2:
            logger.warning("At least 2 data inputs required for merging. Returning empty DataFrame.")
            df = DataFrame(pd.DataFrame())
            self.status = df
            return df

        operation = MergeOperation(self.operation)
        try:
            logger.info(f"Processing merge operation: {operation}")
            df = self._process_operation(operation)
            df = DataFrame(df)
            self.status = df
            return df
        except Exception as e:
            logger.error(f"Error during {operation} operation: {str(e)}")
            raise

    def _process_operation(self, operation: MergeOperation) -> pd.DataFrame:
        """Processes data according to the selected merge operation.

        Args:
            operation: The merge operation to perform.

        Returns:
            pd.DataFrame: The merged data as a pandas DataFrame.
        """
        if operation == MergeOperation.CONCATENATE:
            return self._concatenate_data()
        elif operation == MergeOperation.APPEND:
            return self._append_data()
        elif operation == MergeOperation.MERGE:
            return self._merge_data()
        elif operation == MergeOperation.JOIN:
            return self._join_data()
        
        logger.warning(f"Unsupported operation: {operation}")
        return pd.DataFrame()

    def _concatenate_data(self) -> pd.DataFrame:
        """Combines text values with newlines for each key.

        Returns:
            pd.DataFrame: DataFrame with concatenated text values.
        """
        combined_data = {}
        for data_input in self.data_inputs:
            for key, value in data_input.data.items():
                if key in combined_data:
                    if isinstance(combined_data[key], str) and isinstance(value, str):
                        combined_data[key] = f"{combined_data[key]}\n{value}"
                    else:
                        combined_data[key] = value
                else:
                    combined_data[key] = value
        return pd.DataFrame([combined_data])

    def _append_data(self) -> pd.DataFrame:
        """Adds each data input as a new row.

        Returns:
            pd.DataFrame: DataFrame with appended rows.
        """
        rows = []
        for data_input in self.data_inputs:
            rows.append(data_input.data)
        return pd.DataFrame(rows)

    def _merge_data(self) -> pd.DataFrame:
        """Combines values into lists for each key.

        Returns:
            pd.DataFrame: DataFrame with merged values as lists.
        """
        combined_data = {}
        for data_input in self.data_inputs:
            for key, value in data_input.data.items():
                if key in combined_data and isinstance(value, str):
                    if not isinstance(combined_data[key], list):
                        combined_data[key] = [combined_data[key]]
                    combined_data[key].append(value)
                else:
                    combined_data[key] = value
        return pd.DataFrame([combined_data])

    def _join_data(self) -> pd.DataFrame:
        """Adds columns with suffixes to avoid name conflicts.

        Returns:
            pd.DataFrame: DataFrame with joined columns.
        """
        combined_data = {}
        for idx, data_input in enumerate(self.data_inputs, 1):
            for key, value in data_input.data.items():
                new_key = f"{key}_doc{idx}" if idx > 1 else key
                combined_data[new_key] = value
        return pd.DataFrame([combined_data])
