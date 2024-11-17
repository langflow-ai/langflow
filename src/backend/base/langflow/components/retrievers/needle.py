from typing import cast

from langchain_community.retrievers.needle import NeedleRetriever

from langflow.custom import CustomComponent
from langflow.field_typing import Retriever


class NeedleRetrieverComponent(CustomComponent):
    display_name: str = "Needle Retriever"
    description: str = "Retriever that uses the Needle API to search collections."
    name = "NeedleRetriever"
    icon = "search"
    legacy: bool = True

    def build_config(self):
        """Defines the configuration options for the NeedleRetriever component."""
        return {
            "needle_api_key": {
                "display_name": "Needle API Key",
                "field_type": "password",
            },
            "collection_id": {"display_name": "Collection ID"},
            "top_k": {
                "display_name": "Top K Results",
                "field_type": "int",
                "value": 10,
            },
            "code": {"show": False},  # Internal field, hidden from the UI
        }

    def build(
        self,
        needle_api_key: str,
        collection_id: str,
        top_k: int = 10,
    ) -> Retriever:  # type: ignore[type-var]
        """Build the NeedleRetriever using the provided configuration.

        Args:
            needle_api_key (str): The API key for Needle.
            collection_id (str): The ID of the Needle collection to search.
            top_k (int): The maximum number of results to retrieve.

        Returns:
            Retriever: An instance of the NeedleRetriever.
        """
        try:
            # Initialize the NeedleRetriever
            output = NeedleRetriever(
                needle_api_key=needle_api_key,
                collection_id=collection_id,
                top_k=top_k,
            )
        except Exception as e:
            msg = "Could not connect to the Needle API. Please verify your credentials."
            raise ValueError(msg) from e

        # Cast the output to Retriever and return it
        return cast(Retriever, output)
