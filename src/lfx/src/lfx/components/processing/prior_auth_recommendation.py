from typing import Any

from lfx.io import MultilineInput, Output
from lfx.schema.data import Data
from loguru import logger

from lfx.base.modelhub import ATModelComponent
from langflow.custom.genesis.services.deps import get_rag_service


class PriorAuthRecommendation(ATModelComponent):
    """Component for generating prior authorization recommendations"""

    display_name: str = "Prior Auth Recommendation"
    description: str = (
        "Generate recommendations based on guidelines and medical history"
    )
    documentation: str = "https://docs.example.com/prior-auth"
    icon: str = "Autonomize"
    name: str = "PriorAuthRecommendation"

    inputs = [
        MultilineInput(
            name="medical_history",
            display_name="Medical History",
            value="",
            info="The medical history of the patient.",
            required=True,
        ),
        MultilineInput(
            name="guidelines",
            display_name="Guidelines",
            value="",
            info="The guidelines to follow for the recommendation.",
            required=True,
        ),
    ]

    outputs = [
        Output(
            name="recommendation", display_name="Recommendation", method="build_output"
        )
    ]

    async def generate_recommendation(
        self, medical_history: str, guidelines: str
    ) -> Any:
        """Generate recommendation using the RAG service"""
        try:
            logger.debug(f"Medical History: {medical_history}")
            logger.debug(f"Guidelines: {guidelines}")

            payload = {"medical_history": medical_history, "guidelines": [guidelines]}
            response = await get_rag_service().generate_guideline_adjudication_summary(
                payload
            )
            return response
        except Exception as e:
            logger.error(f"Error generating recommendation: {e!s}")
            raise ValueError(f"Failed to generate recommendation: {e!s}") from e

    async def build_output(self) -> Data:
        """Generate the output recommendation"""
        recommendation = await self.generate_recommendation(
            medical_history=self.medical_history, guidelines=self.guidelines
        )
        data = Data(value=recommendation)
        self.status = data
        return data
