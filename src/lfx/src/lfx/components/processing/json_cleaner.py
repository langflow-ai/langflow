import json
import re
import unicodedata

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, MessageTextInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class JSONCleaner(Component):
    icon = "braces"
    display_name = "JSON Cleaner"
    description = (
        "Cleans the messy and sometimes incorrect JSON strings produced by LLMs "
        "so that they are fully compliant with the JSON spec."
    )
    legacy = True
    replacement = ["processing.ParserComponent"]
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
        """Clean the input JSON string based on provided options and return the cleaned JSON string."""
        try:
            from json_repair import repair_json
        except ImportError as e:
            msg = "Could not import the json_repair package. Please install it with `pip install json_repair`."
            raise ImportError(msg) from e

        json_str = self.json_str
        remove_control_chars = self.remove_control_chars
        normalize_unicode = self.normalize_unicode
        validate_json = self.validate_json

        span = self._find_json_span(json_str)
        if span is None:
            msg = "Invalid JSON string: no JSON object or array found"
            raise ValueError(msg)
        start, end = span
        try:
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
            msg = f"Error cleaning JSON string: {e}"
            raise ValueError(msg) from e

    @staticmethod
    def _find_json_span(s: str) -> tuple[int, int] | None:
        """Return an enclosing array or the existing object span.

        For array-only input, prefer payloads over bracketed prose labels ending
        with a colon. Preserve a leading array or the first candidate as fallback.
        """
        object_span = (s.find("{"), s.rfind("}"))
        has_object = -1 not in object_span
        first_array_span = None
        content_start = len(s) - len(s.lstrip())
        array_start = -1
        depth = 0
        quoted_string = re.compile(r"""(?<![\w\\])(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""", re.DOTALL)
        index = 0
        while index < len(s):
            if depth and (quoted := quoted_string.match(s, index)):
                # Leave unmatched quotes and unquoted apostrophes for json_repair.
                index = quoted.end()
                continue
            char = s[index]
            if char == "[":
                if depth == 0:
                    array_start = index
                depth += 1
            elif char == "]" and depth:
                depth -= 1
                if depth == 0:
                    if has_object:
                        if array_start < object_span[0] and index > object_span[1]:
                            return array_start, index
                    else:
                        if first_array_span is None:
                            first_array_span = (array_start, index)
                        following = index + 1
                        while following < len(s) and s[following].isspace():
                            following += 1
                        if array_start == content_start or following == len(s) or s[following] != ":":
                            return array_start, index
            index += 1
        if has_object:
            return object_span
        return first_array_span

    def _remove_control_characters(self, s: str) -> str:
        """Remove control characters from the string."""
        return s.translate(self.translation_table)

    def _normalize_unicode(self, s: str) -> str:
        """Normalize Unicode characters in the string."""
        return unicodedata.normalize("NFC", s)

    def _validate_json(self, s: str) -> str:
        """Validate the JSON string."""
        try:
            json.loads(s)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON string: {e}"
            raise ValueError(msg) from e
        return s

    def __init__(self, *args, **kwargs):
        # Create a translation table that maps control characters to None
        super().__init__(*args, **kwargs)
        self.translation_table = str.maketrans("", "", "".join(chr(i) for i in range(32)) + chr(127))
