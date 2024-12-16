from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field, create_model

from langflow.base.models.chat_result import get_chat_result
from langflow.custom import Component
from langflow.helpers.base_model import build_model_from_schema
from langflow.io import BoolInput, HandleInput, MessageTextInput, Output, StrInput, TableInput
from langflow.schema.data import Data

if TYPE_CHECKING:
    from langflow.field_typing.constants import LanguageModel


class StructuredOutputComponent(Component):
    display_name = "Structured Output"
    description = (
        "Transforms LLM responses into **structured data formats**. Ideal for extracting specific information "
        "or creating consistent outputs."
    )
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
        ),
        StrInput(
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
        BoolInput(
            name="multiple",
            advanced=True,
            display_name="Generate Multiple",
            info="Set to True if the model should generate a list of outputs instead of a single output.",
        ),
    ]

    outputs = [
        Output(name="structured_output", display_name="Structured Output", method="build_structured_output"),
    ]

    def build_structured_output(self) -> Data:
        if not hasattr(self.llm, "with_structured_output"):
            msg = "Language model does not support structured output."
            raise TypeError(msg)
        if not self.output_schema:
            msg = "Output schema cannot be empty"
            raise ValueError(msg)

        output_model_ = build_model_from_schema(self.output_schema)
        if self.multiple:
            output_model = create_model(
                self.schema_name,
                objects=(list[output_model_], Field(description=f"A list of {self.schema_name}.")),  # type: ignore[valid-type]
            )
        else:
            output_model = output_model_
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
        output = get_chat_result(runnable=llm_with_structured_output, input_value=self.input_value, config=config_dict)
        if isinstance(output, BaseModel):
            output_dict = output.model_dump()
        else:
            msg = f"Output should be a Pydantic BaseModel, got {type(output)} ({output})"
            raise TypeError(msg)
        return Data(data=output_dict)
