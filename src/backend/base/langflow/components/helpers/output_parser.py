from langchain_core.output_parsers import CommaSeparatedListOutputParser

from langflow.custom.custom_component.component import Component
from langflow.field_typing.constants import OutputParser
from langflow.io import DropdownInput, Output
from langflow.schema.message import Message


class OutputParserComponent(Component):
    display_name = "Output Parser"
    description = "Transforms the output of an LLM into a specified format."
    icon = "type"
    name = "OutputParser"
    legacy = True

    inputs = [
        DropdownInput(
            name="parser_type",
            display_name="Parser",
            options=["CSV"],
            value="CSV",
        ),
    ]

    outputs = [
        Output(
            display_name="Format Instructions",
            name="format_instructions",
            info="Pass to a prompt template to include formatting instructions for LLM responses.",
            method="format_instructions",
        ),
        Output(display_name="Output Parser", name="output_parser", method="build_parser"),
    ]

    def build_parser(self) -> OutputParser:
        if self.parser_type == "CSV":
            return CommaSeparatedListOutputParser()
        msg = "Unsupported or missing parser"
        raise ValueError(msg)

    def format_instructions(self) -> Message:
        if self.parser_type == "CSV":
            return Message(text=CommaSeparatedListOutputParser().get_format_instructions())
        msg = "Unsupported or missing parser"
        raise ValueError(msg)
