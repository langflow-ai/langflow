import ast
import json

from langflow.custom import CustomComponent
from langflow.schema import Record


class JSONInputComponent(CustomComponent):
    display_name = "JSON Input"
    description = "Load a JSON object as input."

    def build_config(self):
        return {
            "json_str": {
                "display_name": "JSON String",
                "multiline": True,
                "info": "The JSON string to load.",
            }
        }

    def build(self, json_str: str) -> Record:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                data = ast.literal_eval(json_str)
            except (SyntaxError, ValueError):
                raise ValueError("Invalid JSON string.")
        record = Record(data=data)
        return record
