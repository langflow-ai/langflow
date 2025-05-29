from collections.abc import AsyncIterator, Iterator
from typing import Any

from langflow.custom import Component
from langflow.io import HandleInput, Output, TabInput
from langflow.schema import Data, DataFrame, Message
from langflow.services.database.models.message.model import MessageBase


# def get_message_converter(v) -> Message:
#     # If v is a instance of Message, then its fine
#     if isinstance(v, dict):
#         return Message(**v)
#     if isinstance(v, Message):
#         return v
#     if isinstance(v, str | AsyncIterator | Iterator):
#         return Message(text=v)
#     if isinstance(v, MessageBase):
#         return Message(**v.model_dump())
#     if isinstance(v, DataFrame):
#         # Process DataFrame similar to the _safe_convert method
#         # Remove empty rows
#         processed_df = v.dropna(how="all")
#         # Remove empty lines in each cell
#         processed_df = processed_df.replace(r"^\s*$", "", regex=True)
#         # Replace multiple newlines with a single newline
#         processed_df = processed_df.replace(r"\n+", "\n", regex=True)
#         # Replace pipe characters to avoid markdown table issues
#         processed_df = processed_df.replace(r"\|", r"\\|", regex=True)
#         processed_df = processed_df.map(lambda x: str(x).replace("\n", "<br/>") if isinstance(x, str) else x)
#         # Convert to markdown and wrap in a Message
#         return Message(text=processed_df.to_markdown(index=False))
#     if isinstance(v, Data):
#         if v.text_key in v.data:
#             return Message(text=v.get_text())
#         return Message(text=str(v.data))
#     msg = f"Invalid value type {type(v)}"
#     raise ValueError(msg)


# def get_data_converter(v: DataFrame | Data | Message | dict) -> Data:
#     """Get the data conversion dispatcher."""
#     if isinstance(v, DataFrame):
#         # Convert DataFrame to a list of dictionaries and wrap in a Data object
#         dict_list = v.to_dict(orient="records")
#         return Data(data={"results": dict_list})
#     if isinstance(v, Message):
#         return Data(data=v.data)
#     if isinstance(v, dict):
#         return Data(data=v)
#     if not isinstance(v, Data):
#         msg = f"Invalid value type {type(v)} for input Expected Data."
#         raise ValueError(msg)  # noqa: TRY004
#     return v


# def get_dataframe_converter(v: DataFrame | Data | Message | dict) -> DataFrame:
#     """Get the dataframe conversion dispatcher."""
#     if isinstance(v, Data):
#         data_dict = v.data
#         # If data contains only one key and the value is a list of dictionaries, convert to DataFrame
#         if (
#             len(data_dict) == 1
#             and isinstance(next(iter(data_dict.values())), list)
#             and all(isinstance(item, dict) for item in next(iter(data_dict.values())))
#         ):
#             return DataFrame(data=next(iter(data_dict.values())))
#         return DataFrame(data=[v])
#     if isinstance(v, Message):
#         return DataFrame(data=[v])
#     if isinstance(v, dict):
#         return DataFrame(data=[v])
#     if not isinstance(v, DataFrame):
#         msg = f"Invalid value type {type(v)}. Expected DataFrame."
#         raise ValueError(msg)  # noqa: TRY004
#     return v


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
        return Message(text=self.input_data)

    def convert_to_data(self) -> Data:
        """Convert input to Data type."""
        return Data(data=self.input_data)

    def convert_to_dataframe(self) -> DataFrame:
        """Convert input to DataFrame type."""
        return DataFrame(self.input_data)
