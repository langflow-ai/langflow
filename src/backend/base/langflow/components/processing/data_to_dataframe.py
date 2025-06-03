from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data, DataFrame


class DataToDataFrameComponent(Component):
    display_name = "Data → DataFrame"
    description = (
        "Converts one or multiple Data objects into a DataFrame. "
        "Each Data object corresponds to one row. Fields from `.data` become columns, "
        "and the `.text` (if present) is placed in a 'text' column."
    )
    icon = "table"
    name = "DataToDataFrame"
    legacy = True

    inputs = [
        DataInput(
            name="data_list",
            display_name="Data or Data List",
            info="One or multiple Data objects to transform into a DataFrame.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(
            display_name="DataFrame",
            name="dataframe",
            method="build_dataframe",
            info="A DataFrame built from each Data object's fields plus a 'text' column.",
        ),
    ]

    def build_dataframe(self) -> DataFrame:
        """Builds a DataFrame from Data objects by combining their fields.

        For each Data object:
          - Merge item.data (dictionary) as columns
          - If item.text is present, add 'text' column

        Returns a DataFrame with one row per Data object.
        """
        data_input = self.data_list

        # If user passed a single Data, it might come in as a single object rather than a list
        if not isinstance(data_input, list):
            data_input = [data_input]

        rows = []
        for item in data_input:
            if not isinstance(item, Data):
                msg = f"Expected Data objects, got {type(item)} instead."
                raise TypeError(msg)

            # Start with a copy of item.data or an empty dict
            row_dict = dict(item.data) if item.data else {}

            # If the Data object has text, store it under 'text' col
            text_val = item.get_text()
            if text_val:
                row_dict["text"] = text_val

            rows.append(row_dict)

        # Build a DataFrame from these row dictionaries
        df_result = DataFrame(rows)
        self.status = df_result  # store in self.status for logs
        return df_result
