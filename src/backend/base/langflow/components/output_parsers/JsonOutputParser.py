from langflow.base.io.text import TextComponent
from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import MessageInput
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message
from langchain_core.output_parsers import BaseOutputParser, JsonOutputParser
import json


# TODO: We could make a single dynamic Output Parser
# But for now, let's start with one class.
class JSONOutputParserComponent(Component):
    display_name = "JSON Output Parser"
    description = "Pass to a model to parse the output as JSON."
    icon = "type"
    name = "JSONOutputParser"

    inputs = (
        []
    )  # TODO: possibly a pydanitc model for the JSON schema # custom python class input?
    outputs = [
        Output(
            display_name="Format Instructions",
            name="format_instructions",
            info="Pass to a prompt template to include formatting instructions for LLM responses",
            method="format_instructions",
        ),
        Output(
            display_name="Output Parser", name="output_parser", method="build_parser"
        ),
    ]

    def build_parser(self) -> BaseOutputParser:
        return JsonOutputParser()

    def format_instructions(self) -> Message:
        return Message(text=JsonOutputParser().get_format_instructions())
