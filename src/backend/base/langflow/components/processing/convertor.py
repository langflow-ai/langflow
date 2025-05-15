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

    def convert_to_message(self) -> Message:
        """Convert input to Message type."""
        return get_message_converter(self.input_data)

    def convert_to_data(self) -> Data:
        """Convert input to Data type."""
        return get_data_converter(self.input_data)

    def convert_to_dataframe(self) -> DataFrame:
        """Convert input to DataFrame type."""
        return get_dataframe_converter(self.input_data)
