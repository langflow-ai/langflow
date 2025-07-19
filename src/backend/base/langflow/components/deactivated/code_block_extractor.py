import re

from lfx.custom.custom_component.component import Component

from langflow.field_typing import Input, Output, Text


class CodeBlockExtractor(Component):
    display_name = "Code Block Extractor"
    description = "Extracts code block from text."
    name = "CodeBlockExtractor"

    inputs = [Input(name="text", field_type=Text, description="Text to extract code blocks from.")]

    outputs = [Output(name="code_block", display_name="Code Block", method="get_code_block")]

    def get_code_block(self) -> Text:
        text = self.text.strip()
        # Extract code block
        # It may start with ``` or ```language
        # It may end with ```
        pattern = r"^```(?:\w+)?\s*\n(.*?)(?=^```)```"
        match = re.search(pattern, text, re.MULTILINE)
        code_block = ""
        if match:
            code_block = match.group(1)
        return code_block
