"""SemanticMap component for generating new data following the specified schema using LLM instructions."""

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
from pydantic import create_model



class SemanticMap(BaseAgenticComponent):
    """Process each row or item with an LLM using natural language instructions to generate output data following the specified schema."""

    display_name = "Semantic Map"
    description = "Process each row or item with an LLM using natural language instructions to generate output data following the specified schema."
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Data Input",
            info="DataFrame or a batch of structured data",            
        ),
        get_generated_fields_input(),
        BoolInput(name="return_multiple_instances",
                  display_name="Generate Multiple Outputs",
                  info="If enabled, generate multiple instances of the specified type",
                  advanced=False,
                  value=False,
                  ),
        BoolInput(
            name="concatenate_generated_lists",
            display_name="Flatten Generated Outputs",
            info="If enabled, flatten multiple outputs into a single output",
            value=True,
            advanced=True,
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Natural language instructions to map your input data to the output schema",
            value="",
        ),
       
        BoolInput(
            name="append_to_input_columns",
            display_name="Keep Source Columns",
            info="If disabled, returns only new columns. Otherwise, keep the input columns in the output",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Data Output",
            info="The resulting data processed by the LLM that follows the output schema",
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
        if self.return_multiple_instances:
            FinalAtype = create_model(
                f"ListOfTarget",
                items=(list[atype], ...)
            )
        else: 
            FinalAtype= atype

        target = AG(
            atype=FinalAtype,
            transduction_type=TRANSDUCTION_AMAP,
            llm=llm,
        )
        if "{" in self.instructions:
            source.prompt_template = self.instructions
        else:
            source.instructions += self.instructions

        output = await (target << source)
        if self.concatenate_generated_lists and self.return_multiple_instances:
            appended_states = []
            
            for state in output:
                for item_state in state.items:
                    appended_states.append(item_state)
                    
            output=AG(atype=atype,states = appended_states)
           
        elif self.append_to_input_columns:
            output = source.merge_states(output)

        return DataFrame(output.to_dataframe().to_dict(orient="records"))
