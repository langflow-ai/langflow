"""SemanticFilter component for filtering DataFrame rows using LLM predicates."""

from __future__ import annotations

from lfx.components.agentics.base_component import BaseAgenticComponent
from lfx.components.agentics.constants import ERROR_AGENTICS_NOT_INSTALLED
from lfx.components.agentics.helpers import prepare_llm_from_component
from lfx.components.agentics.inputs import get_model_provider_inputs
from lfx.io import (
    DataFrameInput,
    IntInput,
    MessageTextInput,
    Output,
)
from lfx.schema.dataframe import DataFrame


class SemanticFilter(BaseAgenticComponent):
    """Filters DataFrame rows based on a semantic predicate evaluated by an LLM."""

    display_name = "SemanticFilter"
    description = "Reads each of the input rows and filters those matching the provided predicate template"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

    inputs = [
        *get_model_provider_inputs(),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        MessageTextInput(
            name="predicate_template",
            display_name="Predicate Template",
            info="The predicate condition to filter rows by",
            value="",
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
            method="semantic_filter",
            tool_mode=True,
        ),
    ]

    async def semantic_filter(self) -> DataFrame:
        """Filter DataFrame rows based on the predicate template."""
        try:
            from agentics import AG
            from agentics.core.semantic_operators import sem_filter
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        llm = prepare_llm_from_component(self)

        source = AG.from_dataframe(DataFrame(self.source))
        output = await sem_filter(
            source,
            self.predicate_template,
            batch_size=self.batch_size,
            llm=llm,
        )

        return output.to_dataframe().to_dict(orient="records")
