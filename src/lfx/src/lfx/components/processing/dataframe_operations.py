import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.inputs import SortableListInput
from lfx.io import BoolInput, DataFrameInput, DropdownInput, IntInput, MessageTextInput, Output, StrInput
from lfx.log.logger import logger
from lfx.schema.dataframe import DataFrame


class DataFrameOperationsComponent(Component):
    display_name = "Table Operations"
    description = "Perform various operations on a Table."
    documentation: str = "https://docs.langflow.org/dataframe-operations"
    icon = "table"
    name = "DataFrameOperations"
    metadata = {
        "keywords": [
            "dataframe",
            "dataframe operations",
            "table",
            "table operations",
            "filter",
            "sort",
            "merge",
            "concatenate",
            "drop column",
            "rename column",
            "add column",
            "select columns",
            "replace value",
            "drop duplicates",
        ],
    }

    OPERATION_CHOICES = [
        "Add Column",
        "Concatenate",
        "Drop Column",
        "Filter",
        "Head",
        "Merge",
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
            display_name="Table",
            info="The input DataFrame to operate on. Connect multiple DataFrames for merge or concatenate operations.",
            required=True,
            is_list=True,
        ),
        SortableListInput(
            name="operation",
            display_name="Operation",
            placeholder="Select Operation",
            info="Select the DataFrame operation to perform.",
            options=[
                {"name": "Add Column", "icon": "plus"},
                {"name": "Concatenate", "icon": "combine"},
                {"name": "Drop Column", "icon": "minus"},
                {"name": "Filter", "icon": "filter"},
                {"name": "Head", "icon": "arrow-up"},
                {"name": "Merge", "icon": "merge"},
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
            options=[
                "equals",
                "not equals",
                "contains",
                "not contains",
                "starts with",
                "ends with",
                "greater than",
                "less than",
            ],
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
        StrInput(
            name="merge_on_column",
            display_name="Merge On Column",
            info="The column name to merge DataFrames on. Must exist in both DataFrames.",
            dynamic=True,
            show=False,
        ),
        DropdownInput(
            name="merge_how",
            display_name="Merge Type",
            options=["inner", "outer", "left", "right"],
            value="inner",
            info="Type of merge: inner (intersection), outer (union), left, or right.",
            dynamic=True,
            show=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Table",
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
            "merge_on_column",
            "merge_how",
        ]
        for field in dynamic_fields:
            build_config[field]["show"] = False

        if field_name == "operation":
            # Handle SortableListInput format
            if isinstance(field_value, list):
                operation_name = field_value[0].get("name", "") if field_value else ""
            else:
                operation_name = field_value or ""

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
            elif operation_name == "Merge":
                build_config["merge_on_column"]["show"] = True
                build_config["merge_how"]["show"] = True

        return build_config

    def _get_primary_dataframe(self) -> DataFrame:
        """Get the first DataFrame from input (handles both single and list inputs)."""
        if isinstance(self.df, list):
            return self.df[0].copy() if self.df else DataFrame()
        return self.df.copy()

    def perform_operation(self) -> DataFrame:
        df_copy = self._get_primary_dataframe()

        # Handle SortableListInput format for operation (also supports legacy string format)
        operation_input = getattr(self, "operation", [])
        if isinstance(operation_input, list):
            op = operation_input[0].get("name", "") if operation_input else ""
        else:
            op = operation_input or ""

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
        if op == "Concatenate":
            return self.concatenate_dataframes()
        if op == "Merge":
            return self.merge_dataframes()
        msg = f"Unsupported operation: {op}"
        logger.error(msg)
        raise ValueError(msg)

    def filter_rows_by_value(self, df: DataFrame) -> DataFrame:
        column = df[self.column_name]
        filter_value = self.filter_value

        # Handle regular DropdownInput format (just a string value)
        operator = getattr(self, "filter_operator", "equals")  # Default to equals for backward compatibility

        if operator == "equals":
            mask = column == filter_value
        elif operator == "not equals":
            mask = column != filter_value
        elif operator == "contains":
            mask = column.astype(str).str.contains(str(filter_value), na=False)
        elif operator == "not contains":
            mask = ~column.astype(str).str.contains(str(filter_value), na=False)
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

    def concatenate_dataframes(self) -> DataFrame:
        """Concatenate multiple DataFrames vertically (stack rows)."""
        if not isinstance(self.df, list) or len(self.df) == 0:
            return self.df.copy() if self.df is not None else DataFrame()

        # If only one DataFrame, return it
        if len(self.df) == 1:
            return self.df[0].copy()

        # Concatenate all DataFrames vertically
        concatenated = pd.concat(self.df, ignore_index=True)
        return DataFrame(concatenated)

    def merge_dataframes(self) -> DataFrame:
        """Merge two DataFrames based on a common column (join operation)."""
        if not isinstance(self.df, list) or len(self.df) == 0:
            return self.df.copy() if self.df is not None else DataFrame()

        # If only one DataFrame, return it
        if len(self.df) == 1:
            return self.df[0].copy()

        # Merge requires exactly two DataFrames
        max_merge_inputs = 2
        if len(self.df) > max_merge_inputs:
            msg = f"Merge requires exactly {max_merge_inputs} DataFrames, got {len(self.df)}"
            raise ValueError(msg)

        df1 = self.df[0].copy()
        df2 = self.df[1].copy()

        merge_on = getattr(self, "merge_on_column", None)
        merge_how = getattr(self, "merge_how", "inner")

        # If merge column specified, validate it exists in both DataFrames
        if merge_on:
            if merge_on not in df1.columns:
                msg = f"Column '{merge_on}' not found in first DataFrame. Available: {list(df1.columns)}"
                raise ValueError(msg)
            if merge_on not in df2.columns:
                msg = f"Column '{merge_on}' not found in second DataFrame. Available: {list(df2.columns)}"
                raise ValueError(msg)

            merged = df1.merge(df2, on=merge_on, how=merge_how, suffixes=("", "_df2"))
        else:
            merged = df1.merge(df2, left_index=True, right_index=True, how=merge_how, suffixes=("", "_df2"))

        # Combine duplicate columns: use df1 value if exists, otherwise df2 value
        cols_to_drop = []
        for col in merged.columns:
            if col.endswith("_df2"):
                original_col = col[:-4]  # Remove "_df2" suffix
                if original_col in merged.columns:
                    # Coalesce: use original if not null, otherwise use _df2
                    merged[original_col] = merged[original_col].combine_first(merged[col])
                    cols_to_drop.append(col)

        if cols_to_drop:
            merged = merged.drop(columns=cols_to_drop)

        return DataFrame(merged)
