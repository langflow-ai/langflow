import json
from typing import Any

from langflow.base.processing.type_conversion import (
    get_data_converter,
    get_dataframe_converter,
    get_message_converter,
)
from langflow.custom import Component
from langflow.io import HandleInput, Output, TabInput
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message


class TypeConverterComponent(Component):
    display_name = "Type Convert"
    description = "Convert between different types (Message, Data, DataFrame)"
    icon = "repeat"

    # Class-level conversion dispatchers
    _message_converters = get_message_converter()
    _data_converters = get_data_converter()
    _dataframe_converters = get_dataframe_converter()

    inputs = [
        HandleInput(
            name="input_data",
            display_name="Input",
            input_types=["Message", "Data", "DataFrame"],
            info="Accept Message, Data or DataFrame as input",
            required=True,
        ),
        TabInput(
            name="output_type",
            display_name="Output Type",
            options=["Message", "Data", "DataFrame"],
            info="Select the desired output data type",
            real_time_refresh=True,
            value="Message",
        ),
    ]

    outputs = [Output(display_name="Message Output", name="message_output", method="convert_to_message")]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "output_type":
            # Start with empty outputs
            frontend_node["outputs"] = []

            # Add only the selected output type
            if field_value == "Message":
                frontend_node["outputs"].append(
                    Output(display_name="Message Output", name="message_output", method="convert_to_message").to_dict()
                )
            elif field_value == "Data":
                frontend_node["outputs"].append(
                    Output(display_name="Data Output", name="data_output", method="convert_to_data").to_dict()
                )
            elif field_value == "DataFrame":
                frontend_node["outputs"].append(
                    Output(
                        display_name="DataFrame Output", name="dataframe_output", method="convert_to_dataframe"
                    ).to_dict()
                )

        return frontend_node

    def _safe_convert(self, data: Any) -> str:
        """Safely convert input data to string."""
        try:
            if isinstance(data, str):
                return data
            if isinstance(data, Message):
                return data.get_text()
            if isinstance(data, Data):
                return json.dumps(data.data)
            if isinstance(data, DataFrame):
                # Remove empty rows
                data = data.dropna(how="all")
                # Remove empty lines in each cell
                data = data.replace(r"^\s*$", "", regex=True)
                # Replace multiple newlines with a single newline
                data = data.replace(r"\n+", "\n", regex=True)
                return data.to_markdown(index=False)
            return str(data)
        except (ValueError, TypeError, AttributeError) as e:
            msg = f"Error converting data: {e!s}"
            raise ValueError(msg) from e

    def convert_to_message(self) -> Message:
        """Convert input data to string with proper error handling."""
        result = ""
        if isinstance(self.input_data, list):
            result = "\n".join([self._safe_convert(item) for item in self.input_data])
        else:
            result = self._safe_convert(self.input_data)
        self.log(f"Converted to string with length: {len(result)}")
        message = Message(text=result)
        self.status = message
        return message

    def convert_to_data(self) -> Data:
        """Convert input to Data type."""
        input_data = self.input_data

        converter = self._data_converters.get(type(input_data))
        if converter:
            try:
                return converter(input_data)
            except (ValueError, TypeError, AttributeError) as e:
                self.log(f"Error converting to Data: {e!s}")
                return Data(data={"text": str(input_data)})

        # Default fallback
        return Data(data={"value": str(input_data)})

    def convert_to_dataframe(self) -> DataFrame:
        """Convert input to DataFrame type."""
        input_data = self.input_data
        converter = self._dataframe_converters.get(type(input_data))
        if converter:
            try:
                return converter(input_data)
            except (ValueError, TypeError, AttributeError) as e:
                self.log(f"Error converting to DataFrame: {e!s}")
                import pandas as pd

                return DataFrame.from_pandas(pd.DataFrame({"value": [str(input_data)]}))

        # Default fallback
        import pandas as pd

        return DataFrame.from_pandas(pd.DataFrame({"value": [str(input_data)]}))
