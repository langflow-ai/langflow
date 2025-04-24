from typing import Any

from langflow.custom import Component
from langflow.io import HandleInput, Output, TabInput
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message


class DataTypeConverterComponent(Component):
    display_name = "Data Type Converter"
    description = "Convert between different data types (Message, Data, DataFrame)"
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
            value="Message",
            info="Select the desired output data type",
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(display_name="Message Output", name="message_output", method="to_message"),
        Output(display_name="Data Output", name="data_output", method="to_data"),
        Output(display_name="DataFrame Output", name="dataframe_output", method="to_dataframe"),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "output_type":
            # Start with empty outputs
            frontend_node["outputs"] = []

            # Add only the selected output type
            if field_value == "Message":
                frontend_node["outputs"].append(
                    Output(display_name="Message Output", name="message_output", method="to_message").to_dict()
                )
            elif field_value == "Data":
                frontend_node["outputs"].append(
                    Output(display_name="Data Output", name="data_output", method="to_data").to_dict()
                )
            elif field_value == "DataFrame":
                frontend_node["outputs"].append(
                    Output(display_name="DataFrame Output", name="dataframe_output", method="to_dataframe").to_dict()
                )

        return frontend_node

    def to_message(self) -> Message:
        """Convert input to Message type."""
        input_data = self.input_data

        if isinstance(input_data, Message):
            return input_data

        if isinstance(input_data, Data):
            # Convert Data to a string representation and create a Message
            try:
                import json

                text = json.dumps(input_data.data)
                return Message(text=text)
            except Exception as e:
                self.log(f"Error converting Data to Message: {e!s}")
                return Message(text=str(input_data.data))

        if isinstance(input_data, DataFrame):
            # Convert DataFrame to markdown and create a Message
            try:
                text = input_data.to_markdown(index=False)
                return Message(text=text)
            except Exception as e:
                self.log(f"Error converting DataFrame to Message: {e!s}")
                return Message(text=str(input_data))

        # Default fallback
        return Message(text=str(input_data))

    def to_data(self) -> Data:
        """Convert input to Data type."""
        input_data = self.input_data

        if isinstance(input_data, Data):
            return input_data

        if isinstance(input_data, Message):
            # Create a Data object with the message text
            try:
                import json

                # Try to parse as JSON first
                try:
                    data_dict = json.loads(input_data.get_text())
                    return Data(data=data_dict)
                except json.JSONDecodeError:
                    # If not valid JSON, use text as is
                    return Data(data={"text": input_data.get_text()})
            except Exception as e:
                self.log(f"Error converting Message to Data: {e!s}")
                return Data(data={"text": str(input_data)})

        if isinstance(input_data, DataFrame):
            # Convert DataFrame to a dictionary for Data
            try:
                data_dict = input_data.to_dict(orient="records")
                return Data(data={"records": data_dict})
            except Exception as e:
                self.log(f"Error converting DataFrame to Data: {e!s}")
                return Data(data={"text": str(input_data)})

        # Default fallback
        return Data(data={"value": str(input_data)})

    def to_dataframe(self) -> DataFrame:
        """Convert input to DataFrame type."""
        input_data = self.input_data

        if isinstance(input_data, DataFrame):
            return input_data

        if isinstance(input_data, Message):
            # Try to convert message text to DataFrame
            try:
                import json

                import pandas as pd

                text = input_data.get_text()
                # Try to parse as JSON
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        return DataFrame.from_pandas(pd.DataFrame(data))
                    if isinstance(data, dict):
                        return DataFrame.from_pandas(pd.DataFrame([data]))
                    # Single value, create a simple DataFrame
                    return DataFrame.from_pandas(pd.DataFrame({"value": [data]}))
                except json.JSONDecodeError:
                    # Not JSON, create a simple text DataFrame
                    return DataFrame.from_pandas(pd.DataFrame({"text": [text]}))
            except Exception as e:
                self.log(f"Error converting Message to DataFrame: {e!s}")
                return DataFrame.from_pandas(pd.DataFrame({"text": [str(input_data)]}))

        if isinstance(input_data, Data):
            # Convert Data to DataFrame
            try:
                import pandas as pd

                data = input_data.data
                if isinstance(data, dict):
                    return DataFrame.from_pandas(pd.DataFrame([data]))
                if isinstance(data, list):
                    return DataFrame.from_pandas(pd.DataFrame(data))
                return DataFrame.from_pandas(pd.DataFrame({"value": [data]}))
            except Exception as e:
                self.log(f"Error converting Data to DataFrame: {e!s}")
                return DataFrame.from_pandas(pd.DataFrame({"value": [str(input_data)]}))

        # Default fallback
        import pandas as pd

        return DataFrame.from_pandas(pd.DataFrame({"value": [str(input_data)]}))
