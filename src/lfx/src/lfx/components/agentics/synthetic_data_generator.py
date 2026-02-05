"""SyntheticDataGenerator component for generating synthetic data using LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.components.agentics.base_component import BaseAgenticComponent
from lfx.components.agentics.constants import ERROR_AGENTICS_NOT_INSTALLED
from lfx.components.agentics.helpers import (
    build_schema_fields,
    prepare_llm_from_component,
)
from lfx.components.agentics.inputs import (
    get_generated_fields_input,
    get_model_provider_inputs,
)
from lfx.io import (
    IntInput,
    Output,
)

if TYPE_CHECKING:
    from lfx.schema.dataframe import DataFrame


class SyntheticDataGenerator(BaseAgenticComponent):
    """Generate synthetic data based on the required schema."""

    display_name = "SyntheticDataGen"
    description = "Generate fake data for the required schema"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        get_generated_fields_input(
            name="schema",
            display_name="Generated Fields",
            info="Define the structure and data types for the model's output.",
        ),
        IntInput(
            name="batch_size",
            display_name="Number of Instances",
            value=10,
            advanced=False,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Target DataFrame",
            method="generate",
            tool_mode=True,
        ),
    ]

    async def generate(self) -> DataFrame:
        """Execute transduction on the source DataFrame."""
        try:
            from agentics import AG
            from agentics.core.atype import create_pydantic_model
            from agentics.core.transducible_functions import generate_prototypical_instances
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        llm = prepare_llm_from_component(self)

        schema_fields = build_schema_fields(self.schema)
        atype = create_pydantic_model(schema_fields, name="GeneratedData")

        output_states = await generate_prototypical_instances(
            atype,
            n_instances=self.batch_size,
            llm=llm,
        )
        output = AG(states=output_states)

        return output.to_dataframe().to_dict(orient="records")
