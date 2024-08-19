import json
import re
import unicodedata
from langflow.custom import Component
from langflow.inputs import MessageTextInput, BoolInput
from langflow.template import Output
from langflow.schema.message import Message


class JSONCleaner(Component):
    display_name = "JSON Cleaner"
    description = "Cleans the messy and sometimes incorrect JSON strings produced by LLMs so that they are fully compliant with the JSON spec."
    icon = "custom_components"

    inputs = [
        MessageTextInput(
            name="json_str", display_name="JSON String", info="The JSON string to be cleaned.", required=True
        ),
        BoolInput(
            name="remove_control_chars",
            display_name="Remove Control Characters",
            info="Remove control characters from the JSON string.",
            required=False,
        ),
        BoolInput(
            name="normalize_unicode",
            display_name="Normalize Unicode",
            info="Normalize Unicode characters in the JSON string.",
            required=False,
        ),
        BoolInput(
            name="validate_json",
            display_name="Validate JSON",
            info="Validate the JSON string to ensure it is well-formed.",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Cleaned JSON String", name="output", method="clean_json"),
    ]

    def clean_json(self) -> Message:
        try:
            from json_repair import repair_json  # type: ignore
        except ImportError:
            raise ImportError(
                "Could not import the json_repair package." "Please install it with `pip install json_repair`."
            )

        """Clean the input JSON string based on provided options and return the cleaned JSON string."""
        json_str = self.json_str
        remove_control_chars = self.remove_control_chars
        normalize_unicode = self.normalize_unicode
        validate_json = self.validate_json

        try:
            start = json_str.find("{")
            end = json_str.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("Invalid JSON string: Missing '{' or '}'")
            json_str = json_str[start : end + 1]

            if remove_control_chars:
                json_str = self._remove_control_characters(json_str)
            if normalize_unicode:
                json_str = self._normalize_unicode(json_str)
            if validate_json:
                json_str = self._validate_json(json_str)

            cleaned_json_str = repair_json(json_str)
            result = str(cleaned_json_str)

            self.status = result
            return Message(text=result)
        except Exception as e:
            raise ValueError(f"Error cleaning JSON string: {str(e)}")

    def _remove_control_characters(self, s: str) -> str:
        """Remove control characters from the string."""
        return re.sub(r"[\x00-\x1F\x7F]", "", s)

    def _normalize_unicode(self, s: str) -> str:
        """Normalize Unicode characters in the string."""
        return unicodedata.normalize("NFC", s)

    def _validate_json(self, s: str) -> str:
        """Validate the JSON string."""
        try:
            json.loads(s)
            return s
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {str(e)}")
