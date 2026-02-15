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
from pydantic import create_model



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
        BoolInput(name="return_multiple_instances",
                  display_name="return_multiple_instances",
                  info="If True, return multiple instances of the specified type for each row.",
                  advanced=False,
                  value=False,
                  ),
        BoolInput(
            name="concatenate_generated_lists",
            display_name="Concatenate Generated Lists",
            info="If true and the Return Multiple Instances is set to True, concatenate all the generate instances in a single dataframe of the defined schema",
            value=True,
            advanced=True,
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Instructions for generating the new column values",
            value="",
        ),
       
        BoolInput(
            name="append_to_input_columns",
            display_name="Return Source Columns",
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
