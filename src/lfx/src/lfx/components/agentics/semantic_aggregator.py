"""SemanticAggregator component for aggregating DataFrame rows using LLM."""

from __future__ import annotations

from lfx.components.agentics.base_component import BaseAgenticComponent
from lfx.components.agentics.constants import (
    ERROR_AGENTICS_NOT_INSTALLED,
    TRANSDUCTION_AREDUCE,
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
    DataFrameInput,
    MessageTextInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class SemanticAggregator(BaseAgenticComponent):
    """Generate a single row with the required field based on the analysis of the entire dataframe."""

    display_name = "Semantic Aggregator"
    description = "Generate a single row with the required field based on the analysis of the entire dataframe"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
            required=True,
        ),
        get_generated_fields_input(),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Instructions for generating the new column values",
            advanced=True,
            value="",
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Target DataFrame",
            method="semantic_aggregation",
            tool_mode=True,
        ),
    ]

    async def semantic_aggregation(self) -> DataFrame:
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
            transduction_type=TRANSDUCTION_AREDUCE,
            instructions=self.instructions,
            llm=llm,
        )

        output = await (target << source)

        return output.to_dataframe().to_dict(orient="records")
