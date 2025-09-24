from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from loguru import logger


class EntityNormalisationExtraction(Component):
    display_name = "Entity Normalisation Extraction"
    description = "Identifies and extracts entities with medical codes."
    icon = "Autonomize"
    name = "EntityNormalizationExtraction"

    inputs = [
        DataInput(
            name="data",
            display_name="Data",
            info="Entity prediction data",
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Filtered Entities",
            name="filtered_entities",
            method="process_entities",
        ),
    ]

    def process_entities(self) -> Data:
        try:
            data = self.data.data
            if isinstance(data, dict) and "value" in data:
                data = data["value"]

            logger.debug(f"Processing data: {data}")
            output = []

            for entity in data:
                if (
                    entity.get("ICD10CMConcepts")
                    or entity.get("CPT_Current_Procedural_Terminology")
                    or entity.get("RxNormConcepts")
                ):
                    output.append(entity)

            logger.debug(f"Found {len(output)} entities with medical codes")
            return Data(value={"data": output})

        except Exception as e:
            logger.error(f"Error processing entities: {e!s}")
            raise ValueError(f"Error processing entities: {e!s}")
