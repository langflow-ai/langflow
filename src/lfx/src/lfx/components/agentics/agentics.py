"""Agentics component for data transformation using an LLM and natural language instructions with desired schema.
Process a large batch of data in Map/Reduce style computation for concurrent and faster processing.
"""

from __future__ import annotations

from lfx.components.agentics.base_component import BaseAgenticComponent
from lfx.components.agentics.constants import (
    ERROR_AGENTICS_NOT_INSTALLED,
    TRANSDUCTION_AMAP,
    TRANSDUCTION_GENERATE,
    TRANSDUCTION_TYPES,
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
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class AgenticsComponent(BaseAgenticComponent):
    """Uses an LLM to transform a large batch of data defined by the data type and natural langauge instructions."""

    display_name = "Agentic Data Transducer"
    description = (
        "Uses an LLM to transform a large batch of data defined by the data type and natural langauge instructions."
    )
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Input DataFrame",
            info="The input schema is inferred from columns",
        ),
        DropdownInput(
            name="transduction_type",
            display_name="Transduction Mode",
            info="Choose how to process input data. amap transforms each row or item, areduce aggregates all rows, and generate creates a batch of data",
            options=TRANSDUCTION_TYPES,
            value=TRANSDUCTION_AMAP,
            required=True,
        ),
        MessageTextInput(
            name="atype_name",
            display_name="Output Schema Name",
            info="Give a descriptive name for the output data",
            value="",
            required=True,
        ),
        get_generated_fields_input(),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Natural language instruction to transform your input data to output schema",
            value="",
        ),
        BoolInput(
            name="merge_source",
            display_name="Keep Input Data",
            info="When enabled, the output data will include input data columns. Disable to return only generated data columns",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            info="Number of rows or items to process at once. In generate mode, this is the number of rows or items to create",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Output DataFrame",
            info="The resulting DataFrame processed by the LLM that follows the output schema",
            method="transduce",
            tool_mode=True,
        ),
    ]

    async def transduce(self) -> DataFrame:
        """Execute transduction on the source DataFrame."""
        try:
            from agentics import AG
            from agentics.core.atype import create_pydantic_model
            from agentics.core.transducible_functions import generate_prototypical_instances
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        llm = prepare_llm_from_component(self)

        schema_fields = build_schema_fields(self.schema)
        atype = create_pydantic_model(schema_fields, name=self.atype_name)

        source = AG.from_dataframe(DataFrame(self.source))

        if self.transduction_type == TRANSDUCTION_GENERATE:
            output_states = await generate_prototypical_instances(
                atype,
                n_instances=self.batch_size,
                llm=llm,
            )
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
            if self.merge_source and self.transduction_type == TRANSDUCTION_AMAP:
                output = source.merge_states(output)

        return DataFrame(output.to_dataframe().to_dict(orient="records"))
