from __future__ import annotations

from lfx.base.models.unified_models import (
    get_language_model_options,
    update_model_options_in_build_config,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataFrameInput,
    DropdownInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    ModelInput,
    Output,
    SecretStrInput,
    StrInput,
    TableInput,
)
from lfx.schema.dataframe import DataFrame
from lfx.schema.table import EditMode

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class DataFrameOps(Component):
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
            options=["merge", "compose", "concatenate"],
            value="ammergeap",
            required=True,
        ),
    ]

    outputs = [
        Output(name="states", display_name="Target DataFrame", method="dataframe_operations", tool_mode=True),
    ]
    async def dataframe_operations(self) -> DataFrame:
        """Process each row in df[column_name] with the language model asynchronously."""
        try:
            from agentics import AG
        except ImportError as e:
            msg = "Agentics-py is not installed. Please install it with `uv pip install agentics-py`."
            raise ImportError(msg) from e
        
        left = AG.from_dataframe(DataFrame(self.left_dataframe))
        right = AG.from_dataframe(DataFrame(self.right_dataframe))

        if self.operation_type == "merge":
            output = left.merge_states(right)
        elif self.operation_type == "compose":
            output = left.compose_states(right)
        elif self.operation_type == "concatenate":
            output_states= left.states + right.states
            output = AG(states=output_states)
        else:
            raise ValueError(f"Unsupported operation type: {self.operation_type}")
        
        return output.to_dataframe().to_dict(orient="records")
