"""Defines the Langflow component for interacting with an embedding model."""

from typing import Any

from lfx.inputs.inputs import FieldTypes
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data

from lfx.base.modelhub import ATModelComponent
from langflow.custom.genesis.services.modelhub.model_endpoint import ModelEndpoint


class EmbeddingComponent(ATModelComponent):
    """Component for the Embedding model"""

    display_name: str = "Autonomize Embedding"
    category: str = "embeddings"
    description: str = "Model for embedding data"
    documentation: str = "https://docs.example.com/clinical-llm"
    icon: str = "Autonomize"
    name: str = "Embedding"
    _model_name = ModelEndpoint.EMBEDDING
    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search query",
            field_type=FieldTypes.TEXT,
            multiline=True,
        )
    ]

    outputs = [
        Output(name="embedding", display_name="Embedding", method="build_output"),
    ]

    async def create_embedding(self, text) -> Any:
        """
        Extract embeddings from the input text
        Args:
            text: The text to extract embeddings from
        Returns:
            The embeddings for the input text
        """
        try:
            response = await self.predict(text=text)
            return response
        except Exception as e:
            msg = f"Error extracting clinical entities: {e!s}"
            raise ValueError(msg) from e

    async def build_output(self) -> Data:
        """Generate the output based on selected knowledgehub hubs."""
        query_results = await self.create_embedding(self.search_query)
        data = Data(value={"data": query_results})
        self.status = data
        return data
