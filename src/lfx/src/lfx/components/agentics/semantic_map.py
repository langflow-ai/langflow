"""SemanticMap component for generating new columns using LLM instructions."""

from __future__ import annotations

from lfx.components.agentics.base_component import BaseAgenticComponent
from lfx.components.agentics.constants import (
    ERROR_AGENTICS_NOT_INSTALLED,
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
from lfx.io import (
    BoolInput,
    DataFrameInput,
    MessageTextInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class SemanticMap(BaseAgenticComponent):
    """Generates new columns in a DataFrame based on LLM instructions."""

    display_name = "SemanticMap"
    description = "Reads each of the input rows and generates new columns"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        get_generated_fields_input(),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Instructions for generating the new column values",
            value="",
        ),
        BoolInput(
            name="append_to_input_columns",
            display_name="Append To Source Columns",
            info="If false, returns only new columns, append to original data otherwise",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Target DataFrame",
            method="semantic_map",
            tool_mode=True,
        ),
    ]

    async def semantic_map(self) -> DataFrame:
        """Generate new columns based on the provided instructions."""
        try:
            from agentics import AG
            from agentics.core.atype import create_pydantic_model
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        llm = prepare_llm_from_component(self)
        source = AG.from_dataframe(DataFrame(self.source))

        schema_fields = build_schema_fields(self.generated_fields)
        atype = create_pydantic_model(schema_fields, name="Target")

        target = AG(
            atype=atype,
            transduction_type=TRANSDUCTION_AMAP,
            instructions=self.instructions,
            llm=llm,
        )

        output = await (target << source)

        if self.append_to_input_columns:
            output = source.merge_states(output)

        return output.to_dataframe().to_dict(orient="records")
