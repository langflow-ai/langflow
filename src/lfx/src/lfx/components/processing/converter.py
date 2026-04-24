import json
from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, HandleInput, Output, TabInput
from lfx.schema import Data, DataFrame, Message
from lfx.schema.data import JSON
from lfx.schema.dataframe import Table

MIN_CSV_LINES = 2


def convert_to_message(v) -> Message:
    """Convert input to Message type.

    Args:
        v: Input to convert (Message, Data, DataFrame, or dict)

    Returns:
        Message: Converted Message object
    """
    return v if isinstance(v, Message) else v.to_message()


def convert_to_data(v: Table | Data | Message | dict, *, auto_parse: bool) -> JSON:
    """Convert input to JSON type.

    Args:
        v: Input to convert (Message, Data, Table, or dict)
        auto_parse: Enable automatic parsing of structured data (JSON/CSV)

    Returns:
        JSON: Converted JSON object
    """
    if isinstance(v, dict):
        return Data(v)
    if isinstance(v, Message):
        data = Data(data={"text": v.data["text"]})
        return parse_structured_data(data) if auto_parse else data

    return v if isinstance(v, Data) else v.to_data()


def convert_to_dataframe(v: Table | Data | Message | dict, *, auto_parse: bool) -> Table:
    """Convert input to Table type.

    Args:
        v: Input to convert (Message, Data, Table, or dict)
        auto_parse: Enable automatic parsing of structured data (JSON/CSV)

    Returns:
        Table: Converted Table object
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


def parse_structured_data(data: JSON) -> JSON:
    """Parse structured data (JSON, CSV) from JSON's text field.

    Args:
        data: JSON object with text content to parse

    Returns:
        JSON: Modified JSON object with parsed content or original if parsing fails
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


def _try_parse_json(text: str) -> JSON | None:
    """Try to parse text as JSON and return JSON object."""
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            # Single JSON object
            return Data(data=parsed)
        if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
            # Array of JSON objects - create JSON with the list
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


def _parse_csv_to_data(text: str) -> JSON:
    """Parse CSV text and return JSON object."""
    from io import StringIO

    import pandas as pd

    # Parse CSV to DataFrame, then convert to list of dicts
    parsed_df = pd.read_csv(StringIO(text))
    records = parsed_df.to_dict(orient="records")

    return Data(data={"records": records})


class TypeConverterComponent(Component):
    display_name = "Type Convert"
    description = "Convert between different types (Message, JSON, Table)"
    documentation: str = "https://docs.langflow.org/type-convert"
    icon = "repeat"

    inputs = [
        HandleInput(
            name="input_data",
            display_name="Input",
            input_types=["Message", "Data", "JSON", "DataFrame", "Table"],
            info="Accept Message, JSON or Table as input",
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
            options=["Message", "JSON", "Table"],
            info="Select the desired output data type",
            real_time_refresh=True,
            value="Message",
        ),
    ]

    # Define ALL outputs so they exist during validation
    # update_frontend_node will filter to show only the selected one
    outputs = [
        Output(
            display_name="Message Output",
            name="message_output",
            method="convert_to_message",
            types=["Message"],
        ),
        Output(
            display_name="JSON Output",
            name="data_output",
            method="convert_to_data",
            types=["JSON"],
        ),
        Output(
            display_name="Table Output",
            name="dataframe_output",
            method="convert_to_dataframe",
            types=["Table"],
        ),
    ]

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """Ensure outputs are synced with output_type when component is loaded."""
        # Call parent implementation first
        await super().update_frontend_node(new_frontend_node, current_frontend_node)

        # Then sync outputs with current output_type value
        output_type = new_frontend_node.get("template", {}).get("output_type", {}).get("value", "Message")
        self.update_outputs(new_frontend_node, "output_type", output_type)

        return new_frontend_node

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "output_type":
            # Start with empty outputs
            frontend_node["outputs"] = []

            # Add only the selected output type WITH TYPES SPECIFIED
            if field_value == "Message":
                frontend_node["outputs"].append(
                    Output(
                        display_name="Message Output",
                        name="message_output",
                        method="convert_to_message",
                        types=["Message"],
                    ).to_dict()
                )
            elif field_value in ("Data", "JSON"):
                frontend_node["outputs"].append(
                    Output(
                        display_name="JSON Output",
                        name="data_output",
                        method="convert_to_data",
                        types=["JSON"],
                    ).to_dict()
                )
            elif field_value in ("DataFrame", "Table"):
                frontend_node["outputs"].append(
                    Output(
                        display_name="Table Output",
                        name="dataframe_output",
                        method="convert_to_dataframe",
                        types=["Table"],
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

    def convert_to_data(self) -> JSON:
        """Convert input to JSON type."""
        input_value = self.input_data[0] if isinstance(self.input_data, list) else self.input_data

        # Handle string input by converting to Message first
        if isinstance(input_value, str):
            input_value = Message(text=input_value)

        result = convert_to_data(input_value, auto_parse=self.auto_parse)
        self.status = result
        return result

    def convert_to_dataframe(self) -> Table:
        """Convert input to Table type."""
        input_value = self.input_data[0] if isinstance(self.input_data, list) else self.input_data

        # Handle string input by converting to Message first
        if isinstance(input_value, str):
            input_value = Message(text=input_value)

        result = convert_to_dataframe(input_value, auto_parse=self.auto_parse)
        self.status = result
        return result
