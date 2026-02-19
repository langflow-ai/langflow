"""Component for combining two DataFrames with different schemas using various merge strategies."""

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
    """Combine two DataFrames with potentially different schemas using various strategies.
    
    Supports three combination methods:
    - Merge: Creates a unified schema by merging both input schemas
    - Compose: Creates a nested schema pairing input and output schemas
    - Concatenate: Stacks all rows from both DataFrames
    """

    display_name = "DataFrame Combiner"
    description = "Combine two DataFrames with potentially different schemas using merge, compose, or concatenate operations."
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        DataFrameInput(
            name="left_dataframe",
            display_name="Left DataFrame",
            info="The first DataFrame to combine.",
            required=True,
        ),
        DataFrameInput(
            name="right_dataframe",
            display_name="Right DataFrame",
            info="The second DataFrame to combine.",
            required=True,
        ),
        DropdownInput(
            name="operation_type",
            display_name="Combination Method",
            info="Merge: unifies schemas | Compose: creates nested schema | Concatenate: stacks all rows vertically.",
            options=DATAFRAME_OPERATIONS,
            value=OPERATION_MERGE,
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Combined DataFrame",
            info="Combined DataFrame resulting from the selected operation.",
            method="dataframe_operations",
            tool_mode=True,
        ),
    ]

    async def dataframe_operations(self) -> DataFrame:
        """Execute the selected combination operation on two DataFrames.
        
        Returns:
            DataFrame resulting from the merge, compose, or concatenate operation.
        """
        try:
            from agentics import AG
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e
        
        if self.left_dataframe or self.right_dataframe:
            
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
        else: raise ValueError("Both DataFrames should be provided.")
