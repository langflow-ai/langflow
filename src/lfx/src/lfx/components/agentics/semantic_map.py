"""SemanticMap component for transforming each row of input data using LLM-based semantic processing."""

from __future__ import annotations

from typing import ClassVar

from pydantic import create_model

from lfx.components.agentics.constants import (
    ERROR_AGENTICS_NOT_INSTALLED,
    ERROR_INPUT_SCHEMA_REQUIRED,
    TRANSDUCTION_AMAP,
)
from lfx.components.agentics.helpers import (
    build_schema_fields,
    prepare_llm_from_component,
)
from lfx.components.agentics.inputs import (
    get_generated_fields_input,
    get_model_provider_inputs,
)
from lfx.components.agentics.inputs.base_component import BaseAgenticComponent
from lfx.io import (
    BoolInput,
    DataFrameInput,
    MessageTextInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class SemanticMap(BaseAgenticComponent):
    """Transform each row of input data using natural language instructions and a defined output schema.

    This component processes input data row-by-row, applying LLM-based transformations to generate
    new columns or derive insights for each individual record.
    """

    code_class_base_inheritance: ClassVar[str] = "Component"
    display_name = "aMap"
    description = (
        "Augment the input dataframe adding new columns defined in the input schema. "
        "Rows are processed independently and in parallel using LLMs."
    )
    documentation: str = "https://docs.langflow.org/bundles-agentics"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Input DataFrame",
            info=("Input DataFrame to transform. The schema is automatically inferred from column names and types."),
        ),
        get_generated_fields_input(),
        BoolInput(
            name="return_multiple_instances",
            display_name="As List",
            info=(
                "If True, generate multiple instances of the provided schema for each input row concatenating all them."
            ),
            advanced=False,
            value=False,
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Natural language instructions describing how to transform each input row into the output schema.",
            value="",
            required=False,
        ),
        BoolInput(
            name="append_to_input_columns",
            display_name="Keep Source Columns",
            info=(
                "Keep original input columns in the output. If disabled, only newly "
                "generated columns are returned. This is ignored if As List is set to True."
            ),
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Output DataFrame",
            info="Transformed DataFrame resulting from semantic mapping.",
            method="aMap",
            tool_mode=True,
        ),
    ]

    async def aMap(self) -> DataFrame:  # noqa: N802
        """Transform input data row-by-row using LLM-based semantic processing.

        Returns:
            DataFrame with transformed data following the output schema.
        """
        try:
            from agentics import AG
            from agentics.core.atype import create_pydantic_model
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        llm = prepare_llm_from_component(self)
        if self.source and self.schema != []:
            source = AG.from_dataframe(DataFrame(self.source))

            schema_fields = build_schema_fields(self.schema)
            atype = create_pydantic_model(schema_fields, name="Target")
            if self.return_multiple_instances:
                final_atype = create_model("ListOfTarget", items=(list[atype], ...))
            else:
                final_atype = atype

            target = AG(
                atype=final_atype,
                transduction_type=TRANSDUCTION_AMAP,
                llm=llm,
            )
            if "{" in self.instructions:
                source.prompt_template = self.instructions
            else:
                source.instructions += self.instructions

            output = await (target << source)
            if self.return_multiple_instances:
                appended_states = [item_state for state in output for item_state in state.items]
                output = AG(atype=atype, states=appended_states)

            elif self.append_to_input_columns:
                output = source.merge_states(output)

            return DataFrame(output.to_dataframe().to_dict(orient="records"))
        raise ValueError(ERROR_INPUT_SCHEMA_REQUIRED)
