import json
from typing import Union, List
from json_repair import repair_json
from pathlib import Path

from langflow.custom import Component
from langflow.io import FileInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data


class JSONToDataComponent(Component):
    display_name = "JSON to Data"
    description = (
        "Convert a JSON file, JSON from a file path, or a JSON string to a Data object or a list of Data objects"
    )
    icon = "braces"
    beta = True
    name = "JSONtoData"

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

    def convert_json_to_data(self) -> Union[Data, List[Data]]:
        try:
            if sum(bool(field) for field in [self.json_file, self.json_path, self.json_string]) != 1:
                raise ValueError("Please provide exactly one of: JSON file, file path, or JSON string.")

            json_data = None

            if self.json_file:
                resolved_path = self.resolve_path(self.json_file)
                file_path = Path(resolved_path)
                if file_path.suffix.lower() != ".json":
                    raise ValueError("The provided file must be a JSON file.")
                with open(file_path, "r", encoding="utf-8") as jsonfile:
                    json_data = jsonfile.read()

            elif self.json_path:
                file_path = Path(self.json_path)
                if file_path.suffix.lower() != ".json":
                    raise ValueError("The provided file must be a JSON file.")
                with open(file_path, "r", encoding="utf-8") as jsonfile:
                    json_data = jsonfile.read()

            elif self.json_string:
                json_data = self.json_string

            if not json_data:
                raise ValueError("No JSON data provided.")

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
            error_message = f"Invalid JSON or Python literal: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            self.status = error_message
            raise ValueError(error_message) from e
