"""SemanticAggregator component for aggregating input data and generating the output data following the specified schema."""

from __future__ import annotations

from pydantic import create_model

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
    BoolInput,
    DataFrameInput,
    MessageTextInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class SemanticAggregator(BaseAgenticComponent):
    """Aggregate or summarize entire input data following natural langauge instructions and the output schema."""

    display_name = "Semantic Aggregator"
    description = (
        "Aggregate or summarize entire input data following natural langauge instructions and the output schema."
    )
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Input DataFrame",
            info="The input schema is inferred from columns",
            required=True,
        ),
        get_generated_fields_input(),
        BoolInput(
            name="return_multiple_instances",
            display_name="Generate Multiple Outputs",
            info="If enabled, generate multiple instances of the specified type",
            advanced=False,
            value=False,
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Natural language instructions to aggregate your input data to output schema",
            advanced=False,
            value="",
        ),
    ]

    outputs = [
        Output(
            name="states",
            method="semantic_aggregation",
            display_name="Output DataFrame",
            info="The resulting DataFrame processed by the LLM that follows the output schema",
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
        if self.return_multiple_instances:
            FinalAtype = create_model("ListOfTarget", items=(list[atype], ...))
        else:
            FinalAtype = atype

        target = AG(
            atype=FinalAtype,
            transduction_type=TRANSDUCTION_AREDUCE,
            instructions=self.instructions
            if not self.return_multiple_instances
            else "\nGenerate a list of instances of the target type following those instructions : ."
            + self.instructions,
            llm=llm,
        )

        output = await (target << source)
        if self.return_multiple_instances:
            output = AG(atype=atype, states=output[0].items)

        return DataFrame(output.to_dataframe().to_dict(orient="records"))
