import json

from langflow.base.io.text import TextComponent
from langflow.inputs import DataInput
from langflow.io import BoolInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class JSONOutputComponent(TextComponent):
    display_name = "JSON Output"
    description = "Display input data as JSON in the Playground."
    icon = "Braces"
    name = "JSONOutput"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The data to convert to JSON.",
            is_list=True,
        ),
        BoolInput(
            name="pretty_print",
            display_name="Pretty Print",
            info="Format JSON with proper indentation",
            value=True,
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="JSON", name="json", method="json_response"),
    ]

    def _process_data(self, data: Data | list[Data]) -> dict | list:
        """Convert Data object(s) to dictionary/list format."""
        if isinstance(data, list):
            return [item.dict() for item in data]
        return data.dict()

    def json_response(self) -> Message:
        try:
            # Process the Data input
            processed_data = self._process_data(self.data)

            # Convert to JSON string with optional pretty printing
            if self.pretty_print:
                formatted_json = json.dumps(
                    processed_data, indent=2, ensure_ascii=False
                )
            else:
                formatted_json = json.dumps(processed_data, ensure_ascii=False)

            message = Message(text=formatted_json)
            self.status = formatted_json
            return message

        except Exception as e:
            error_message = f"Error processing data to JSON: {e!s}"
            message = Message(text=error_message)
            self.status = error_message
            return message
