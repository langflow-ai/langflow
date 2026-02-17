"""Component for combining two DataFrames, possibly having two different schema. Merge or Compose a new output schema if requested."""

from __future__ import annotations

from lfx.components.agentics.constants import (
    DATAFRAME_OPERATIONS,
    ERROR_AGENTICS_NOT_INSTALLED,
    ERROR_UNSUPPORTED_OPERATION,
    OPERATION_COMPOSE,
    OPERATION_CONCATENATE,
    OPERATION_MERGE,
)
from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataFrameInput,
    DropdownInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class DataFrameOps(Component):
    """Combine two structured DataFrames, possibly with different schema. Merge creates a new output schema by merging input schemas, compose introduces a nested schema of a pair of input and output schema."""

    display_name = "DataFrame Combiner"
    description = "Combine two DataFrames, possibly with different schema."
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        DataFrameInput(
            name="left_dataframe",
            display_name="Left DataFrame",
            info="The first input DataFrame to combine",
        ),
        DataFrameInput(
            name="right_dataframe",
            display_name="Right DataFrame",
            info="The second input DataFrame to combine",
        ),
        DropdownInput(
            name="operation_type",
            display_name="Combination Method",
            info="Merge creates a new output schema by merging input schemas, compose introduces a nested schema of a pair of the input and output schema, and concatenate stacks all the rows",
            options=DATAFRAME_OPERATIONS,
            value=OPERATION_MERGE,
            required=True,
        )
    ]

    outputs = [
        Output(
            name="states",
            display_name="Combined DataFrame",
            info="The resulting DataFrame after combining two input DataFrames",
            method="dataframe_operations",
            tool_mode=True,
        ),
    ]

    async def dataframe_operations(self) -> DataFrame:
        """Execute the selected operation on two DataFrames."""
        try:
            from agentics import AG
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        left = AG.from_dataframe(DataFrame(self.left_dataframe))
        right = AG.from_dataframe(DataFrame(self.right_dataframe))

        if self.operation_type == OPERATION_MERGE:
            output = left.merge_states(right)
        elif self.operation_type == OPERATION_COMPOSE:
            output = left.compose_states(right)
        elif self.operation_type == OPERATION_CONCATENATE:
            output_states = left.states + right.states
            output = AG(states=output_states)
        else:
            raise ValueError(ERROR_UNSUPPORTED_OPERATION.format(operation_type=self.operation_type))

        return DataFrame(output.to_dataframe().to_dict(orient="records"))
