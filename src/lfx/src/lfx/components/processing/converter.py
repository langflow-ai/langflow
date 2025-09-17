import json
from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, HandleInput, Output, TabInput
from lfx.schema import Data, DataFrame, Message

MIN_CSV_LINES = 2


def convert_to_message(v) -> Message:
    """Convert input to Message type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)

    Returns:
        Message: Converted Message object
    """
    return v if isinstance(v, Message) else v.to_message()


def convert_to_data(v: DataFrame | Data | Message | dict, *, auto_parse: bool) -> Data:
    """Convert input to Data type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)
        auto_parse: Enable automatic parsing of structured data (JSON/CSV)

    Returns:
        Data: Converted Data object
    """
    if isinstance(v, dict):
        return Data(v)
    if isinstance(v, Message):
        data = Data(data={"text": v.data["text"]})
        return parse_structured_data(data) if auto_parse else data

    return v if isinstance(v, Data) else v.to_data()


def convert_to_dataframe(v: DataFrame | Data | Message | dict, *, auto_parse: bool) -> DataFrame:
    """Convert input to DataFrame type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)
        auto_parse: Enable automatic parsing of structured data (JSON/CSV)

    Returns:
        DataFrame: Converted DataFrame object
    """
    import pandas as pd

    if isinstance(v, dict):
        return DataFrame([v])
    if isinstance(v, DataFrame):
        return v
    # Handle pandas DataFrame
    if isinstance(v, pd.DataFrame):
        # Convert pandas DataFrame to our DataFrame by creating Data objects
        return DataFrame(data=v)

    if isinstance(v, Message):
        data = Data(data={"text": v.data["text"]})
        return parse_structured_data(data).to_dataframe() if auto_parse else data.to_dataframe()
    # For other types, call to_dataframe method
    return v.to_dataframe()


def parse_structured_data(data: Data) -> Data:
    """Parse structured data (JSON, CSV) from Data's text field.

    Args:
        data: Data object with text content to parse

    Returns:
        Data: Modified Data object with parsed content or original if parsing fails
    """
    raw_text = data.get_text() or ""
    text = raw_text.lstrip("\ufeff").strip()

    # Try JSON parsing first
    parsed_json = _try_parse_json(text)
    if parsed_json is not None:
        return parsed_json

    # Try CSV parsing
    if _looks_like_csv(text):
        try:
            return _parse_csv_to_data(text)
        except Exception:  # noqa: BLE001
            # Heuristic misfire or malformed CSV — keep original data
            return data

    # Return original data if no parsing succeeded
    return data


def _try_parse_json(text: str) -> Data | None:
    """Try to parse text as JSON and return Data object."""
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            # Single JSON object
            return Data(data=parsed)
        if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
            # Array of JSON objects - create Data with the list
            return Data(data={"records": parsed})

    except (json.JSONDecodeError, ValueError):
        pass

    return None


def _looks_like_csv(text: str) -> bool:
    """Simple heuristic to detect CSV content."""
    lines = text.strip().split("\n")
    if len(lines) < MIN_CSV_LINES:
        return False

    header_line = lines[0]
    return "," in header_line and len(lines) > 1


def _parse_csv_to_data(text: str) -> Data:
    """Parse CSV text and return Data object."""
    from io import StringIO

    import pandas as pd

    # Parse CSV to DataFrame, then convert to list of dicts
    parsed_df = pd.read_csv(StringIO(text))
    records = parsed_df.to_dict(orient="records")

    return Data(data={"records": records})


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
        BoolInput(
            name="auto_parse",
            display_name="Auto Parse",
            info="Detect and convert JSON/CSV strings automatically.",
            advanced=True,
            value=False,
            required=False,
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

        result = convert_to_data(input_value, auto_parse=self.auto_parse)
        self.status = result
        return result

    def convert_to_dataframe(self) -> DataFrame:
        """Convert input to DataFrame type."""
        input_value = self.input_data[0] if isinstance(self.input_data, list) else self.input_data

        # Handle string input by converting to Message first
        if isinstance(input_value, str):
            input_value = Message(text=input_value)

        result = convert_to_dataframe(input_value, auto_parse=self.auto_parse)
        self.status = result
        return result
