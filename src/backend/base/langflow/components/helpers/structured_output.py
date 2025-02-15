from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field, create_model

from langflow.base.models.chat_result import get_chat_result
from langflow.custom import Component
from langflow.helpers.base_model import build_model_from_schema
from langflow.io import HandleInput, MessageTextInput, MultilineInput, Output, TableInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame

if TYPE_CHECKING:
    from langflow.field_typing.constants import LanguageModel


class StructuredOutputComponentv2(Component):
    display_name = "Structured Output"
    description = (
        "Transforms LLM responses into **structured data formats**. Ideal for extracting specific information "
        "or creating consistent outputs."
    )
    name = "StructuredOutputv2"
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
                "Extract values accurately and format them according to the specified type (e.g., string, integer, float, date)."
                "If a value is missing or cannot be determined, return a default (e.g., null, 0, or 'N/A')."
                "If multiple instances of the expected structure exist within the input_text, stream each as a separate JSON object."
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
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "description of field",
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "description": (
                        "Indicate the data type of the output field (e.g., str, int, float, bool, list, dict)."
                    ),
                    "default": "text",
                },
                {
                    "name": "multiple",
                    "display_name": "Multiple",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": "False",
                },
            ],
            value=[{"name": "field", "description": "description of field", "type": "text", "multiple": "False"}],
        ),
    ]

    outputs = [
        Output(name="structured_output_data", display_name="Data", method="as_data"),
        Output(name="structured_output_dataframe", display_name="DataFrame", method="as_dataframe"),
    ]

    def build_structured_output(self) -> Data:
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
            objects=(list[output_model_], Field(description=f"A list of {schema_name}.")),  # type: ignore[valid-type]
        )

        try:
            llm_with_structured_output = cast("LanguageModel", self.llm).with_structured_output(schema=output_model)  # type: ignore[valid-type, attr-defined]

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
        if isinstance(result, BaseModel):
            result = result.model_dump()
        if "objects" in result:
            return result["objects"]
        return result

    def as_data(self) -> Data:
        output = self.build_structured_output()

        return Data(results=output)

    def as_dataframe(self) -> DataFrame:
        output = self.build_structured_output()
        if isinstance(output, list):
            return DataFrame(data=output)
        return DataFrame(data=[output])
