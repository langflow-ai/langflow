"""Output parser component for structured LLM response transformation.

This module provides the OutputParserComponent which transforms unstructured
LLM responses into structured formats that can be processed by downstream
components in Langflow workflows.

Supported Parsers:
    - CSV (Comma-Separated Values): Parses LLM output into Python lists
    - Future parsers: JSON, XML, custom formats (extensible design)

Key Features:
    - Format instruction generation for prompts
    - Automatic response parsing and validation
    - Integration with LangChain's output parser ecosystem
    - Structured data output for downstream processing

CSV Parser Functionality:
    - Converts comma-separated text into Python lists
    - Handles quoted values and escaped characters
    - Provides format instructions for LLM prompts
    - Example: "apple, banana, orange" → ["apple", "banana", "orange"]

Component Outputs:
    1. Format Instructions: Text to include in prompts telling the LLM
       how to format its response for successful parsing
    2. Output Parser: The actual parser object for processing responses

Usage Pattern:
    1. Connect format instructions to a prompt template
    2. LLM generates response following the format instructions
    3. Pass LLM response through the output parser
    4. Receive structured data for further processing

Example Format Instructions (CSV):
    "Your response should be a list of comma separated values,
    eg: `foo, bar, baz`"

This component is marked as legacy and may be replaced with more
comprehensive parsing solutions in future versions.
"""

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
