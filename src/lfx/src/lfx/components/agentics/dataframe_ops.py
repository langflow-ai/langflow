"""DataFrameOps component for DataFrame operations."""

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
    """Enables operations between DataFrames: merge, concatenate, composition."""

    display_name = "DataFrameOps"
    description = "Enable Operations between DataFrames: merge, concatenate, composition"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        DataFrameInput(
            name="left_dataframe",
            display_name="Left DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        DataFrameInput(
            name="right_dataframe",
            display_name="Right DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        DropdownInput(
            name="operation_type",
            display_name="Operation Type",
            options=DATAFRAME_OPERATIONS,
            value=OPERATION_MERGE,
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Target DataFrame",
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

        return output.to_dataframe().to_dict(orient="records")
