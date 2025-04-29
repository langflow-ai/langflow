import json

from langflow.schema import Data, DataFrame, Message

# Type conversion dispatchers
_message_converters = {
    Message: lambda msg: Message(text=msg.get_text()),
    Data: lambda data: Message(text=json.dumps(data.data)),
    DataFrame: lambda df: Message(text=df.to_markdown(index=False)),
}

_data_converters = {
    Message: lambda msg: Data(data=msg.data),
    Data: lambda data: data,
    DataFrame: lambda df: Data(data={"records": df.to_dict(orient="records")}),
}

_dataframe_converters = {
    DataFrame: lambda df: df,
    Data: lambda data: DataFrame([dict(data.data) if data.data else {}]),
    Message: lambda msg: DataFrame([dict(msg.data) if msg.data else {}]),
}


def get_message_converter() -> dict:
    """Get the message conversion dispatcher."""
    return _message_converters


def get_data_converter() -> dict:
    """Get the data conversion dispatcher."""
    return _data_converters


def get_dataframe_converter() -> dict:
    """Get the dataframe conversion dispatcher."""
    return _dataframe_converters
