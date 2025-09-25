"""Relation Extraction Component for extracting relationships from structured data."""

from __future__ import annotations

from typing import Any, List

from lfx.custom.custom_component.component import Component
from langflow.helpers.data import data_to_text_list
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from loguru import logger

# If you have a helper for data_to_text_list, import it; otherwise, inline it below.


class RelationExtraction(Component):
    display_name = "Relation Extraction"
    description = "Identifies and extracts relevant lab results from medical records."
    icon = "Autonomize"
    name = "RelationExtraction"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="The data to convert to text.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Data List",
            name="data_list",
            info="Data as a list of new Data, each having `text` formatted by Template",
            method="parse_data_as_list",
        ),
    ]

    def _clean_args(self) -> List[Data]:
        # Accepts both Data and dict, converts dict to Data
        data = self.data if isinstance(self.data, list) else [self.data]
        cleaned = []
        for item in data:
            if isinstance(item, dict):
                cleaned.append(Data(value=item))
            else:
                cleaned.append(item)
        return cleaned

    def parse_data_as_list(self) -> Data:
        data = self._clean_args()
        text_list, data_list = data_to_text_list("{value}", data)
        for item, text in zip(data_list, text_list, strict=True):
            if hasattr(item, "set_text"):
                item.set_text(text)
            else:
                item.data["text"] = text
        extracted_values = self.extract_relations(data_list)
        result = Data(value={"data": extracted_values})
        return result

    def extract_relations(self, data: List[Data]) -> list[Any]:
        relations = []
        for item in data:
            try:
                # Support both dict and object for predictions
                predictions = None
                value_data = item.data["value"]["data"]
                if hasattr(value_data, "prediction"):
                    predictions = value_data.prediction
                elif isinstance(value_data, dict) and "prediction" in value_data:
                    predictions = value_data["prediction"]
                else:
                    logger.warning(f"No 'prediction' found in value_data: {value_data}")
                    continue
                for prediction in predictions:
                    # Support both dict and object for attributes
                    attributes = None
                    if hasattr(prediction, "Attributes"):
                        attributes = getattr(prediction, "Attributes", None)
                    elif isinstance(prediction, dict):
                        attributes = prediction.get("Attributes")
                    if attributes is not None and len(attributes) > 0:
                        relations.append(prediction)
            except Exception as e:
                logger.warning(f"Failed to extract relations: {e}")
        return relations

    def build_output(self) -> Data:
        """Langflow compatibility: standard output method."""
        return self.parse_data_as_list()
