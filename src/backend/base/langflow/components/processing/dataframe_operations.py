import pandas as pd

from langflow.custom.custom_component.component import Component
from langflow.inputs import SortableListInput
from langflow.io import (
    BoolInput,
    DataFrameInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    StrInput,
)
from langflow.logging import logger
from langflow.schema.dataframe import DataFrame


class DataFrameOperationsComponent(Component):
    display_name = "DataFrame Operations"
    description = "Perform various operations on a DataFrame."
    icon = "table"
    name = "DataFrameOperations"

    OPERATION_CHOICES = [
        "Add Column",
        "Drop Column",
        "Filter",
        "Head",
        "Rename Column",
        "Replace Value",
        "Select Columns",
        "Sort",
        "Tail",
        "Drop Duplicates",
    ]

    inputs = [
        DataFrameInput(
            name="df",
            display_name="DataFrame",
            info="The input DataFrame to operate on.",
            required=True,
        ),
        SortableListInput(
            name="operation",
            display_name="Operation",
            placeholder="Select Operation",
            info="Select the DataFrame operation to perform.",
            options=[
                {"name": "Add Column", "icon": "plus"},
                {"name": "Drop Column", "icon": "minus"},
                {"name": "Filter", "icon": "filter"},
                {"name": "Head", "icon": "arrow-up"},
                {"name": "Rename Column", "icon": "pencil"},
                {"name": "Replace Value", "icon": "replace"},
                {"name": "Select Columns", "icon": "columns"},
                {"name": "Sort", "icon": "arrow-up-down"},
                {"name": "Tail", "icon": "arrow-down"},
                {"name": "Drop Duplicates", "icon": "copy-x"},
            ],
            real_time_refresh=True,
            limit=1,
        ),
        StrInput(
            name="column_name",
            display_name="Column Name",
            info="The column name to use for the operation.",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="filter_value",
            display_name="Filter Value",
            info="The value to filter rows by.",
            dynamic=True,
            show=False,
        ),
        DropdownInput(
            name="filter_operator",
            display_name="Filter Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with", "greater than", "less than"],
            value="equals",
            info="The operator to apply for filtering rows.",
            advanced=False,
            dynamic=True,
            show=False,
        ),
        BoolInput(
            name="ascending",
            display_name="Sort Ascending",
            info="Whether to sort in ascending order.",
            dynamic=True,
            show=False,
            value=True,
        ),
        StrInput(
            name="new_column_name",
            display_name="New Column Name",
            info="The new column name when renaming or adding a column.",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="new_column_value",
            display_name="New Column Value",
            info="The value to populate the new column with.",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="columns_to_select",
            display_name="Columns to Select",
            dynamic=True,
            is_list=True,
            show=False,
        ),
        IntInput(
            name="num_rows",
            display_name="Number of Rows",
            info="Number of rows to return (for head/tail).",
            dynamic=True,
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="replace_value",
            display_name="Value to Replace",
            info="The value to replace in the column.",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="replacement_value",
            display_name="Replacement Value",
            info="The value to replace with.",
            dynamic=True,
            show=False,
        ),
    ]

    outputs = [
        Output(
            display_name="DataFrame",
            name="output",
            method="perform_operation",
            info="The resulting DataFrame after the operation.",
        )
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        dynamic_fields = [
            "column_name",
            "filter_value",
            "filter_operator",
            "ascending",
            "new_column_name",
            "new_column_value",
            "columns_to_select",
            "num_rows",
            "replace_value",
            "replacement_value",
        ]
        for field in dynamic_fields:
            build_config[field]["show"] = False

        if field_name == "operation":
            # Handle SortableListInput format
            if isinstance(field_value, list):
                if len(field_value) > 0:
                    operation_name = field_value[0].get('name', '')
                else:
                    # Handle empty selection (user deselected)
                    operation_name = ''
            else:
                operation_name = field_value or ''
                
            # If no operation selected, all dynamic fields stay hidden (already set to False above)
            if not operation_name:
                return build_config
                
            if operation_name == "Filter":
                build_config["column_name"]["show"] = True
                build_config["filter_value"]["show"] = True
                build_config["filter_operator"]["show"] = True
            elif operation_name == "Sort":
                build_config["column_name"]["show"] = True
                build_config["ascending"]["show"] = True
            elif operation_name == "Drop Column":
                build_config["column_name"]["show"] = True
            elif operation_name == "Rename Column":
                build_config["column_name"]["show"] = True
                build_config["new_column_name"]["show"] = True
            elif operation_name == "Add Column":
                build_config["new_column_name"]["show"] = True
                build_config["new_column_value"]["show"] = True
            elif operation_name == "Select Columns":
                build_config["columns_to_select"]["show"] = True
            elif operation_name in {"Head", "Tail"}:
                build_config["num_rows"]["show"] = True
            elif operation_name == "Replace Value":
                build_config["column_name"]["show"] = True
                build_config["replace_value"]["show"] = True
                build_config["replacement_value"]["show"] = True
            elif operation_name == "Drop Duplicates":
                build_config["column_name"]["show"] = True

        return build_config

    def perform_operation(self) -> DataFrame:
        df_copy = self.df.copy()
        
        # Handle SortableListInput format for operation
        operation_input = getattr(self, 'operation', [])
        if isinstance(operation_input, list) and len(operation_input) > 0:
            op = operation_input[0].get('name', '')
        else:
            op = ''
            
        # If no operation selected, return original DataFrame
        if not op:
            return df_copy

        if op == "Filter":
            return self.filter_rows_by_value(df_copy)
        if op == "Sort":
            return self.sort_by_column(df_copy)
        if op == "Drop Column":
            return self.drop_column(df_copy)
        if op == "Rename Column":
            return self.rename_column(df_copy)
        if op == "Add Column":
            return self.add_column(df_copy)
        if op == "Select Columns":
            return self.select_columns(df_copy)
        if op == "Head":
            return self.head(df_copy)
        if op == "Tail":
            return self.tail(df_copy)
        if op == "Replace Value":
            return self.replace_values(df_copy)
        if op == "Drop Duplicates":
            return self.drop_duplicates(df_copy)
        msg = f"Unsupported operation: {op}"
        logger.error(msg)
        raise ValueError(msg)

    def filter_rows_by_value(self, df: DataFrame) -> DataFrame:
        column = df[self.column_name]
        filter_value = self.filter_value
        
        # Handle regular DropdownInput format (just a string value)
        operator = getattr(self, 'filter_operator', 'equals')  # Default to equals for backward compatibility
        
        if operator == "equals":
            mask = column == filter_value
        elif operator == "not equals":
            mask = column != filter_value
        elif operator == "contains":
            mask = column.astype(str).str.contains(str(filter_value), na=False)
        elif operator == "starts with":
            mask = column.astype(str).str.startswith(str(filter_value), na=False)
        elif operator == "ends with":
            mask = column.astype(str).str.endswith(str(filter_value), na=False)
        elif operator == "greater than":
            try:
                # Try to convert filter_value to numeric for comparison
                numeric_value = pd.to_numeric(filter_value)
                mask = column > numeric_value
            except (ValueError, TypeError):
                # If conversion fails, compare as strings
                mask = column.astype(str) > str(filter_value)
        elif operator == "less than":
            try:
                # Try to convert filter_value to numeric for comparison
                numeric_value = pd.to_numeric(filter_value)
                mask = column < numeric_value
            except (ValueError, TypeError):
                # If conversion fails, compare as strings
                mask = column.astype(str) < str(filter_value)
        else:
            mask = column == filter_value  # Fallback to equals
            
        return DataFrame(df[mask])

    def sort_by_column(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.sort_values(by=self.column_name, ascending=self.ascending))

    def drop_column(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.drop(columns=[self.column_name]))

    def rename_column(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.rename(columns={self.column_name: self.new_column_name}))

    def add_column(self, df: DataFrame) -> DataFrame:
        df[self.new_column_name] = [self.new_column_value] * len(df)
        return DataFrame(df)

    def select_columns(self, df: DataFrame) -> DataFrame:
        columns = [col.strip() for col in self.columns_to_select]
        return DataFrame(df[columns])

    def head(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.head(self.num_rows))

    def tail(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.tail(self.num_rows))

    def replace_values(self, df: DataFrame) -> DataFrame:
        df[self.column_name] = df[self.column_name].replace(self.replace_value, self.replacement_value)
        return DataFrame(df)

    def drop_duplicates(self, df: DataFrame) -> DataFrame:
        return DataFrame(df.drop_duplicates(subset=self.column_name))
