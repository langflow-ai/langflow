from __future__ import annotations

from typing import Any

import toml  # type: ignore[import-untyped]
from agentics import AG
from agentics.core.atype import create_pydantic_model
from agentics.core.transducible_functions import generate_prototypical_instances
from crewai import LLM
from lfx.base.models.unified_models import (
    get_language_model_options,
    get_model_classes,
    update_model_options_in_build_config,
)
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataFrameInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    Output,
    SecretStrInput,
    TableInput,
)
from lfx.schema.dataframe import DataFrame
from lfx.schema.table import EditMode


class Agentics(Component):
    display_name = "Agentics"
    description = "Enables Map Reduce Style Agentic data transformations amongs dataframes"
    documentation: str = "github.com/IBM/agentics/"
    icon = "List"

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
        ),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        DropdownInput(
            name="transduction_type",
            display_name="transduction_type",
            options=["amap", "areduce", "generate"],
            value="amap",
            required=True,
        ),
        MessageTextInput(
            name="atype_name",
            display_name="Generated Type",
            info="Provide a name for the generated target type",
            value="",
            required=True,
            # advanced=True,
        ),
        TableInput(
            name="schema",
            display_name="Generated Fields",
            info="Define the structure and data types for the model's output.",
            required=True,
            # TODO: remove deault value
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "text",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "",
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
                    "default": False,
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "name": "text",
                    "description": "",
                    "type": "str",
                    "multiple": False,
                }
            ],
        ),
        MessageTextInput(
            name="instructions",
            display_name="instructions",
            value="",
        ),
        BoolInput(name="merge_source", display_name="merge_source_states", value=True, advanced=True),
        IntInput(name="batch_size", display_name="Batch Size", value=10, advanced=True),
    ]

    outputs = [
        Output(name="states", display_name="Target DataFrame", method="transduce", tool_mode=True),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        return update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

    def _format_row_as_toml(self, row: dict[str, Any]) -> str:
        """Convert a dictionary (row) into a TOML-formatted string."""
        formatted_dict = {str(col): {"value": str(val)} for col, val in row.items()}
        return toml.dumps(formatted_dict)

    def _create_base_row(
        self, original_row: dict[str, Any], model_response: str = "", batch_index: int = -1
    ) -> dict[str, Any]:
        """Create a base row with original columns and additional metadata."""
        row = original_row.copy()
        row[self.output_column_name] = model_response
        row["batch_index"] = batch_index
        return row

    def _add_metadata(
        self, row: dict[str, Any], *, success: bool = True, system_msg: str = "", error: str | None = None
    ) -> None:
        """Add metadata to a row if enabled."""
        if not self.enable_metadata:
            return

        if success:
            row["metadata"] = {
                "has_system_message": bool(system_msg),
                "input_length": len(row.get("text_input", "")),
                "response_length": len(row[self.output_column_name]),
                "processing_status": "success",
            }
        else:
            row["metadata"] = {
                "error": error,
                "processing_status": "failed",
            }

    async def transduce(self) -> DataFrame:
        """Process each row in df[column_name] with the language model asynchronously."""
        # Check if model is already an instance (for testing) or needs to be instantiated
        llm = None
        if isinstance(self.model, list):
            # Extract model configuration
            model_selection = self.model[0]
            model_name = model_selection.get("name")
            provider = model_selection.get("provider")
            metadata = model_selection.get("metadata", {})

            # Get model class and parameters from metadata
            model_class = get_model_classes().get(metadata.get("model_class"))
            if model_class is None:
                msg = f"No model class defined for {model_name}"
                raise ValueError(msg)

            # Get API key from global variables
            from lfx.base.models.unified_models import get_api_key_for_provider

            api_key = get_api_key_for_provider(self.user_id, provider, self.api_key)

            if not api_key and provider != "Ollama":
                msg = f"{provider} API key is required. Please configure it globally."
                raise ValueError(msg)

            if provider == "IBM WatsonX":
                llm = LLM(
                    model="watsonx/" + model_name,
                    base_url="https://us-south.ml.cloud.ibm.com",
                    project_id=self.get_project_name(),
                    api_key=api_key,
                    temperature=0,
                    max_tokens=4000,
                    max_input_tokens=100000,
                )
            elif provider == "Google Generative AI":
                llm = LLM(model="gemini/" + model_name, api_key=api_key)

            else:
                return "Please fix model paramters"

        # print("AAAAAA" , type(self.source))

        # if isinstance(self.source, list):

        source = AG.from_dataframe(DataFrame(self.source))
        schema_fields = [
            (
                field["name"],
                field["description"],
                field["type"] if not field["multiple"] else f"list[{field['type']}]",
                False,
            )
            for field in self.schema
        ]
        atype = create_pydantic_model(schema_fields, name=self.atype_name)
        if self.transduction_type == "generate":
            output_states = await generate_prototypical_instances(atype, n_instances=self.batch_size)
            output = AG(states=output_states)
        else:
            target = AG(
                atype=atype,
                instructions=self.instructions,
                transduction_type=self.transduction_type,
                amap_batch_size=self.batch_size,
                llm=llm,
            )
            output = await (target << source)
            if self.merge_source and self.transduction_type == "amap":
                output = source.merge_states(output)

        df = output.to_dataframe()
        return df.to_dict(orient="records")
