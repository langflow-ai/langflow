import json
from pathlib import Path

from json_repair import repair_json

from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data


class JSONToDataComponent(Component):
    display_name = "Load JSON"
    description = (
        "Convert a JSON file, JSON from a file path, or a JSON string to a Data object or a list of Data objects"
    )
    icon = "braces"
    name = "JSONtoData"
    legacy = True

    inputs = [
        FileInput(
            name="json_file",
            display_name="JSON File",
            file_types=["json"],
            info="Upload a JSON file to convert to a Data object or list of Data objects",
        ),
        MessageTextInput(
            name="json_path",
            display_name="JSON File Path",
            info="Provide the path to the JSON file as pure text",
        ),
        MultilineInput(
            name="json_string",
            display_name="JSON String",
            info="Enter a valid JSON string (object or array) to convert to a Data object or list of Data objects",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="convert_json_to_data"),
    ]

    def convert_json_to_data(self) -> Data | list[Data]:
        if sum(bool(field) for field in [self.json_file, self.json_path, self.json_string]) != 1:
            msg = "Please provide exactly one of: JSON file, file path, or JSON string."
            self.status = msg
            raise ValueError(msg)

        json_data = None

        try:
            if self.json_file:
                resolved_path = self.resolve_path(self.json_file)
                file_path = Path(resolved_path)
                if file_path.suffix.lower() != ".json":
                    self.status = "The provided file must be a JSON file."
                else:
                    json_data = file_path.read_text(encoding="utf-8")

            elif self.json_path:
                file_path = Path(self.json_path)
                if file_path.suffix.lower() != ".json":
                    self.status = "The provided file must be a JSON file."
                else:
                    json_data = file_path.read_text(encoding="utf-8")

            else:
                json_data = self.json_string

            if json_data:
                # Try to parse the JSON string
                try:
                    parsed_data = json.loads(json_data)
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to repair the JSON string
                    repaired_json_string = repair_json(json_data)
                    parsed_data = json.loads(repaired_json_string)

                # Check if the parsed data is a list
                if isinstance(parsed_data, list):
                    result = [Data(data=item) for item in parsed_data]
                else:
                    result = Data(data=parsed_data)
                self.status = result
                return result

        except (json.JSONDecodeError, SyntaxError, ValueError) as e:
            error_message = f"Invalid JSON or Python literal: {e}"
            self.status = error_message
            raise ValueError(error_message) from e

        except Exception as e:
            error_message = f"An error occurred: {e}"
            self.status = error_message
            raise ValueError(error_message) from e

        # An error occurred
        raise ValueError(self.status)
