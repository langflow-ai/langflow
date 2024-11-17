from typing import cast
from langchain_community.retrievers.needle import NeedleRetriever
from langflow.custom import Component
from langflow.inputs import StrInput, IntInput, SecretStrInput
from langflow.template import Output
from langflow.field_typing import Retriever

class NeedleComponent(Component):
    display_name = "Needle Retriever"
    description = "A retriever that uses the Needle API to search collections."
    documentation: str = "https://docs.needle.api/"
    icon = "search"
    name = "NeedleRetriever"

    inputs = [
        SecretStrInput(
            name="needle_api_key",
            display_name="Needle API Key",
            info="The API key to authenticate with the Needle API.",
        ),
        StrInput(
            name="collection_id",
            display_name="Collection ID",
            info="The ID of the Needle collection to search.",
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="The number of results to retrieve.",
            value=10,  # Default value
        ),
    ]

    outputs = [
        Output(display_name="Needle Retriever", name="retriever", method="build_retriever"),
    ]

    def build_retriever(self, needle_api_key: str, collection_id: str, top_k: int = 10) -> Retriever:
        """
        Build and return the NeedleRetriever using the provided inputs.

        Args:
            needle_api_key (str): API key for the Needle API.
            collection_id (str): Collection ID to search in Needle.
            top_k (int): The number of top results to fetch.

        Returns:
            Retriever: A configured NeedleRetriever instance.
        """
        try:
            retriever = NeedleRetriever(
                needle_api_key=needle_api_key,
                collection_id=collection_id,
                top_k=top_k,
            )
        except Exception as e:
            raise ValueError(f"Error initializing NeedleRetriever: {str(e)}")

        return cast(Retriever, retriever)
