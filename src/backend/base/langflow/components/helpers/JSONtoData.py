import json
from typing import Union, List

from langflow.custom import Component
from langflow.io import MessageInput, Output
from langflow.schema import Data


class JSONToDataComponent(Component):
    display_name = "JSON to Data"
    description = "Convert a JSON string to a Data object or a list of Data objects"
    icon = "braces"
    beta = True
    name = "JSONtoData"

    inputs = [
        MessageInput(
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
            json_string = self.json_string.text

            # Try to parse the JSON string
            try:
                parsed_data = json.loads(json_string)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to evaluate it as a Python literal
                import ast

                parsed_data = ast.literal_eval(json_string)

            # Check if the parsed data is a list
            if isinstance(parsed_data, list):
                result = [Data(data=item) for item in parsed_data]
            else:
                result = Data(data=parsed_data)

            self.status = result
            return result

        except (json.JSONDecodeError, SyntaxError, ValueError) as e:
            error_message = f"Invalid JSON or Python literal: {str(e)}"
            error_data = Data(data={"error": error_message})
            self.status = error_data
            return error_data

        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            error_data = Data(data={"error": error_message})
            self.status = error_data
            return error_data
