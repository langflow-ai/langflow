from pydantic import BaseModel, Field, create_model
from trustcall import create_extractor

from langflow.base.models.chat_result import get_chat_result
from langflow.custom.custom_component.component import Component
from langflow.helpers.base_model import build_model_from_schema
from langflow.io import (
    HandleInput,
    MessageTextInput,
    MultilineInput,
    Output,
    TableInput,
)
from langflow.schema.data import Data
from langflow.schema.table import EditMode


class StructuredOutputComponent(Component):
    display_name = "Structured Output"
    description = "Uses an LLM to generate structured data. Ideal for extraction and consistency."
    name = "StructuredOutput"
    icon = "braces"

    inputs = [
        HandleInput(
            name="llm",
            display_name="Language Model",
            info="The language model to use to generate the structured output.",
            input_types=["LanguageModel"],
            required=True,
        ),
        MessageTextInput(
            name="input_value",
            display_name="Input Message",
            info="The input message to the language model.",
            tool_mode=True,
            required=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="Format Instructions",
            info="The instructions to the language model for formatting the output.",
            value=(
                "You are an AI system designed to extract structured information from unstructured text."
                "Given the input_text, return a JSON object with predefined keys based on the expected structure."
                "Extract values accurately and format them according to the specified type "
                "(e.g., string, integer, float, date)."
                "If a value is missing or cannot be determined, return a default "
                "(e.g., null, 0, or 'N/A')."
                "If multiple instances of the expected structure exist within the input_text, "
                "stream each as a separate JSON object."
            ),
            required=True,
            advanced=True,
        ),
        MessageTextInput(
            name="schema_name",
            display_name="Schema Name",
            info="Provide a name for the output data schema.",
            advanced=True,
        ),
        TableInput(
            name="output_schema",
            display_name="Output Schema",
            info="Define the structure and data types for the model's output.",
            required=True,
            # TODO: remove deault value
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "description of field",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate the data type of the output field (e.g., str, int, float, bool, dict)."),
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                },
                {
                    "name": "multiple",
                    "display_name": "As List",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": "False",
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "name": "field",
                    "description": "description of field",
                    "type": "str",
                    "multiple": "False",
                }
            ],
        ),
    ]

    outputs = [
        Output(
            name="structured_output",
            display_name="Structured Output",
            method="build_structured_output",
        ),
    ]

    def build_structured_output_base(self) -> Data:
        schema_name = self.schema_name or "OutputModel"

        if not hasattr(self.llm, "with_structured_output"):
            msg = "Language model does not support structured output."
            raise TypeError(msg)
        if not self.output_schema:
            msg = "Output schema cannot be empty"
            raise ValueError(msg)

        output_model_ = build_model_from_schema(self.output_schema)

        output_model = create_model(
            schema_name,
            __doc__=f"A list of {schema_name}.",
            objects=(list[output_model_], Field(description=f"A list of {schema_name}.")),  # type: ignore[valid-type]
        )

        try:
            llm_with_structured_output = create_extractor(self.llm, tools=[output_model])
        except NotImplementedError as exc:
            msg = f"{self.llm.__class__.__name__} does not support structured output."
            raise TypeError(msg) from exc

        config_dict = {
            "run_name": self.display_name,
            "project_name": self.get_project_name(),
            "callbacks": self.get_langchain_callbacks(),
        }
        result = get_chat_result(
            runnable=llm_with_structured_output,
            system_message=self.system_prompt,
            input_value=self.input_value,
            config=config_dict,
        )

        # OPTIMIZATION NOTE: Simplified result processing logic
        # - Removed unreachable isinstance(result, BaseModel) check since get_chat_result never returns BaseModel
        # - Used early return pattern to reduce nesting

        # Early return for non-dict results
        if not isinstance(result, dict):
            return result

        # Handle responses structure
        if responses := result.get("responses"):
            result = responses[0].model_dump() if isinstance(responses[0], BaseModel) else responses[0]

        # Return objects if present, otherwise the processed result
        return result.get("objects") or result

    def build_structured_output(self) -> Data:
        output = self.build_structured_output_base()
        if not isinstance(output, list) or not output:
            # handle empty or unexpected type case
            msg = "No structured output returned"
            raise ValueError(msg)
        return Data(data=output[-1])
