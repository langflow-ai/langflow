from typing import List, Optional

from langchain_core.embeddings import Embeddings

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Upstash import UpstashVectorStoreComponent
from langflow.field_typing import Text
from langflow.schema import Record


class UpstashSearchComponent(UpstashVectorStoreComponent, LCVectorStoreComponent):
    """
    A custom component for implementing a Vector Store using Upstash.
    """

    display_name: str = "Upstash Search"
    description: str = "Search an Upstash Vector Store for similar documents."

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {
                "display_name": "Embedding",
                "input_types": ["Embeddings"],
                "info": "To use Upstash's embeddings, don't provide an embedding.",
            },
            "index_url": {
                "display_name": "Index URL",
                "info": "The URL of the Upstash index.",
            },
            "index_token": {
                "display_name": "Index Token",
                "info": "The token for the Upstash index.",
            },
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
            "text_key": {
                "display_name": "Text Key",
                "info": "The key in the record to use as text.",
                "advanced": True,
            },
        }

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        search_type: str,
        text_key: str = "text",
        index_url: Optional[str] = None,
        index_token: Optional[str] = None,
        embedding: Optional[Embeddings] = None,
        number_of_results: int = 4,
    ) -> List[Record]:
        vector_store = super().build(
            embedding=embedding,
            text_key=text_key,
            index_url=index_url,
            index_token=index_token,
        )
        if not vector_store:
            raise ValueError("Failed to load the Upstash Vector Store.")

        return self.search_with_vector_store(
            input_value=input_value, search_type=search_type, vector_store=vector_store, k=number_of_results
        )
