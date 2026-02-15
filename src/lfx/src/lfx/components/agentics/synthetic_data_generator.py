"""SyntheticDataGenerator component for generating synthetic data using LLM."""

from __future__ import annotations


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
    MessageTextInput,
    DataFrameInput
)


from lfx.schema.dataframe import DataFrame


class SyntheticDataGenerator(BaseAgenticComponent):
    """Generate synthetic data based on the required schema."""

    display_name = "SyntheticDataGen"
    description = "Generate fake data. If source is provided concatenate more data to source, otherwise uses generates a new dataframe of the given schema"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        get_generated_fields_input(
            name="schema",
            display_name="Schema",
            info="Define the columns that will be generated, providing name, desciption and type for each of them. Used only when source is not provided",
        
        ),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="A dataframe to be used as an example for the syntetic data that will be generated. Only first 50 rows considered",
            required=False,
            advanced=False,
            value=None
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Specific Instructions to drive the  generation of the syntetic data. (Optional)",
            value="",
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Number of Generated Rows",
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
        
        if self.source:
            source = AG.from_dataframe(DataFrame(self.source))
            atype=source.atype
            instructions=str(self.instructions)
            instructions+= "\nHere are examples to take inspiration from" + str(source.states[:50])
        else:
            schema_fields = build_schema_fields(self.schema)
            atype = create_pydantic_model(schema_fields, name="GeneratedData")
            instructions=str(self.instructions)

        output_states = await generate_prototypical_instances(
            atype,
            n_instances=self.batch_size,
            llm=llm,
            instructions=instructions,
        )
        if self.source:
            output_states = source.states + output_states
        output = AG(states=output_states)

        return DataFrame(output.to_dataframe().to_dict(orient="records"))
