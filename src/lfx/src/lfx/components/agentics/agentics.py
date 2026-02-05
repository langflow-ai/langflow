"""Agentics component for Map/Reduce style data transformations."""

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
    """Enables Map Reduce Style Agentic data transformations among dataframes."""

    display_name = "Agentics"
    description = "Enables Map Reduce Style Agentic data transformations among dataframes"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        DropdownInput(
            name="transduction_type",
            display_name="Transduction Type",
            options=TRANSDUCTION_TYPES,
            value=TRANSDUCTION_AMAP,
            required=True,
        ),
        MessageTextInput(
            name="atype_name",
            display_name="Generated Type",
            info="Provide a name for the generated target type",
            value="",
            required=True,
        ),
        get_generated_fields_input(
            name="schema",
            display_name="Generated Fields",
            info="Define the structure and data types for the model's output.",
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            value="",
        ),
        BoolInput(
            name="merge_source",
            display_name="Merge Source States",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Target DataFrame",
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

        return output.to_dataframe().to_dict(orient="records")
