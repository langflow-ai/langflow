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
            info="Select the desired output data type",
            real_time_refresh=True,
        ),
    ]

    outputs = []

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
        print(f"input_data: {input_data}")
        print(f"type(input_data): {type(input_data)}")

        if isinstance(input_data, Message):
            return input_data

        if isinstance(input_data, Data):
            # Convert Data to a string representation and create a Message
            try:
                json_string = input_data.model_dump()
                return Message(text=json_string)
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
        print(f"input_data: {input_data}")
        print(f"type(input_data): {type(input_data)}")

        if isinstance(input_data, Data):
            return input_data

        if isinstance(input_data, Message):
            # Using function from MessageToData component
            print("messag to daata processing")
            print(input_data.data)
            return Data(**input_data.data)

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
        print(f"input_data: {input_data}")
        print(f"type(input_data): {type(input_data)}")

        if isinstance(input_data, DataFrame):
            return input_data

        if isinstance(input_data, Data):
            # Using function from DataToDataFrame component
            data_input = [input_data]
            rows = []

            for item in data_input:
                # Start with a copy of item.data or an empty dict
                row_dict = dict(item.data) if item.data else {}

                # If the Data object has text, store it under 'text' col
                text_val = item.get_text()
                if text_val:
                    row_dict["text"] = text_val

                rows.append(row_dict)

            # Build a DataFrame from these row dictionaries
            df_result = DataFrame(rows)
            return df_result

        if isinstance(input_data, Message):
            # First convert Message to Data
            data_obj = Data(data=input_data.data)

            # Then convert Data to DataFrame
            row_dict = dict(data_obj.data) if data_obj.data else {}
            text_val = data_obj.get_text()
            if text_val:
                row_dict["text"] = text_val

            # Build a DataFrame with a single row
            df_result = DataFrame([row_dict])
            return df_result

        # Default fallback
        import pandas as pd

        return DataFrame.from_pandas(pd.DataFrame({"value": [str(input_data)]}))
