from langflow.custom import Component
from langflow.io import (
    DataInput,
    DataFrameInput,
    MultilineInput,
    DropdownInput,
    Output,
    StrInput,
)
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message


class ParseComponent(Component):
    display_name = "Parse"
    description = (
        "Parse a DataFrame or a Data object into plain text using a specified template. "
        "For DataFrames, column names can be used as keys in the template, e.g., '{col_name}'. "
        "For a Data object, keys like '{text}' or '{data}' can be used."
    )
    icon = "braces"
    name = "Parse"

    inputs = [
        DropdownInput(
            name="input_type",
            display_name="Input Type",
            options=["DataFrame", "Data"],
            value="DataFrame",
            info="Choose whether to parse a DataFrame or a single Data object.",
            required=True,
            real_time_refresh=True,
        ),
        DataFrameInput(
            name="df",
            display_name="DataFrame",
            info="The DataFrame to parse (used when Input Type is 'DataFrame').",
            dynamic=True,
            show=True,
        ),
        DataInput(
            name="data",
            display_name="Data",
            info="A single Data object to parse (used when Input Type is 'Data').",
            dynamic=True,
            show=False,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info=(
                "Template to format the input. For DataFrames, use column names as keys, e.g., '{col_name}'. "
                "For Data, use keys like '{text}', '{data}', or other Data object fields."
            ),
            value="{text}",
        ),
        StrInput(
            name="sep",
            display_name="Separator",
            advanced=True,
            value="\n",
            info="String used to separate rows/items when combining them into a single text.",
        ),
    ]

    outputs = [
        Output(
            display_name="Parsed Text",
            name="parsed_text",
            info="Combined text for all rows/items, formatted by the template and separated by `sep`.",
            method="parse_combined_text",
        ),
        Output(
            display_name="Parsed Texts",
            name="parsed_texts",
            info="A DataFrame with one row per parsed item, containing the formatted text.",
            method="parse_as_dataframe",
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Dynamically update visibility of inputs based on selected input type."""
        if field_name == "input_type":
            if field_value == "DataFrame":
                build_config["df"]["show"] = True
                build_config["data"]["show"] = False
            else:  # Data
                build_config["df"]["show"] = False
                build_config["data"]["show"] = True
        return build_config

    def _clean_args(self):
        """Prepare arguments based on input type."""
        input_type = self.input_type
        if input_type == "DataFrame":
            if not isinstance(self.df, DataFrame):
                raise ValueError("Expected a valid DataFrame for input type 'DataFrame'.")
            return self.df, None, self.template, self.sep
        elif input_type == "Data":
            if not isinstance(self.data, Data):
                raise ValueError("Expected a valid Data object for input type 'Data'.")
            return None, self.data, self.template, self.sep
        else:
            raise ValueError(f"Unsupported input type: {input_type}")

    def parse_combined_text(self) -> Message:
        """Parse all items/rows into a single combined text."""
        df, data, template, sep = self._clean_args()
        lines = []

        if df is not None:
            # Process DataFrame rows
            for _, row in df.iterrows():
                formatted_text = template.format(**row.to_dict())
                lines.append(formatted_text)
        elif data is not None:
            # Process single Data object
            formatted_text = template.format(text=data.get_text())
            lines.append(formatted_text)

        # Combine lines using the separator
        combined_text = sep.join(lines)
        self.status = combined_text
        return Message(text=combined_text)

    def parse_as_dataframe(self) -> DataFrame:
        """Parse all items/rows into a new DataFrame with a single 'parsed_text' column."""
        df, data, template, _ = self._clean_args()
        parsed_rows = []

        if df is not None:
            # Process DataFrame rows
            for _, row in df.iterrows():
                formatted_text = template.format(**row.to_dict())
                parsed_rows.append({"parsed_text": formatted_text})
        elif data is not None:
            # Process single Data object
            formatted_text = template.format(text=data.get_text())
            parsed_rows.append({"parsed_text": formatted_text})

        # Create a new DataFrame from parsed rows
        parsed_df = DataFrame(parsed_rows)
        self.status = parsed_df  # Store for UI logs
        return parsed_df
