from langflow.custom.custom_component.component import Component
from langflow.io import Output
from langflow.schema.message import Message
from langchain_core.output_parsers import CommaSeparatedListOutputParser, BaseOutputParser


class CSVOutputParserComponent(Component):
    display_name = "CSV Output Parser"
    description = "Pass to a model when you want it to return a comma separated list."
    icon = "type"
    name = "CSVOutputParser"

    inputs = []  # no inputs necessary

    outputs = [
        Output(
            display_name="Format Instructions",
            name="format_instructions",
            info="Pass to a prompt template to include formatting instructions for LLM responses.",
            method="format_instructions",
        ),
        Output(display_name="Output Parser", name="output_parser", method="build_parser"),
    ]

    def build_parser(self) -> BaseOutputParser:
        return CommaSeparatedListOutputParser()

    def format_instructions(self) -> Message:
        return Message(text=CommaSeparatedListOutputParser().get_format_instructions())
