from typing import Any

from langflow.custom import Component
from langflow.io import HandleInput, Output, TabInput
from langflow.schema import Data, DataFrame, Message


def convert_to_message(v) -> Message:
    """Convert input to Message type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)

    Returns:
        Message: Converted Message object
    """
    return v if isinstance(v, Message) else v.to_message()


def convert_to_data(v: DataFrame | Data | Message | dict) -> Data:
    """Convert input to Data type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)

    Returns:
        Data: Converted Data object
    """
    if isinstance(v, dict):
        return Data(v)
    if isinstance(v, Message):
        return v.to_data()
    return v if isinstance(v, Data) else v.to_data()


def convert_to_dataframe(v: DataFrame | Data | Message | dict) -> DataFrame:
    """Convert input to DataFrame type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)

    Returns:
        DataFrame: Converted DataFrame object
    """
    if isinstance(v, dict):
        return DataFrame([v])
    return v if isinstance(v, DataFrame) else v.to_dataframe()


class TypeConverterComponent(Component):
    display_name = "Type Convert"
    description = "Convert between different types (Message, Data, DataFrame)"
    documentation: str = "https://docs.langflow.org/components-processing#type-convert"
    icon = "repeat"

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

    outputs = [
        Output(
            display_name="Message Output",
            name="message_output",
            method="convert_to_message",
        )
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "output_type":
            # Start with empty outputs
            frontend_node["outputs"] = []

            # Add only the selected output type
            if field_value == "Message":
                frontend_node["outputs"].append(
                    Output(
                        display_name="Message Output",
                        name="message_output",
                        method="convert_to_message",
                    ).to_dict()
                )
            elif field_value == "Data":
                frontend_node["outputs"].append(
                    Output(
                        display_name="Data Output",
                        name="data_output",
                        method="convert_to_data",
                    ).to_dict()
                )
            elif field_value == "DataFrame":
                frontend_node["outputs"].append(
                    Output(
                        display_name="DataFrame Output",
                        name="dataframe_output",
                        method="convert_to_dataframe",
                    ).to_dict()
                )

        return frontend_node

    def convert_to_message(self) -> Message:
        """Convert input to Message type."""
        input_value = self.input_data[0] if isinstance(self.input_data, list) else self.input_data

        # Handle string input by converting to Message first
        if isinstance(input_value, str):
            input_value = Message(text=input_value)

        result = convert_to_message(input_value)
        self.status = result
        return result

    def convert_to_data(self) -> Data:
        """Convert input to Data type."""
        input_value = self.input_data[0] if isinstance(self.input_data, list) else self.input_data

        # Handle string input by converting to Message first
        if isinstance(input_value, str):
            input_value = Message(text=input_value)

        result = convert_to_data(input_value)
        self.status = result
        return result

    def convert_to_dataframe(self) -> DataFrame:
        """Convert input to DataFrame type."""
        input_value = self.input_data[0] if isinstance(self.input_data, list) else self.input_data

        # Handle string input by converting to Message first
        if isinstance(input_value, str):
            input_value = Message(text=input_value)

        result = convert_to_dataframe(input_value)
        self.status = result
        return result
