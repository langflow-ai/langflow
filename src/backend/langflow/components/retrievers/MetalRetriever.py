from typing import Optional
from langflow import CustomComponent
from langchain.retrievers import MetalRetriever
from langchain.schema import BaseRetriever
from metal_sdk.metal import Metal  # type: ignore


class MetalRetrieverComponent(CustomComponent):
    display_name: str = "Metal Retriever"
    description: str = "Retriever that uses the Metal API."

    def build_config(self):
        return {
            "api_key": {"display_name": "API Key", "password": True},
            "client_id": {"display_name": "Client ID", "password": True},
            "index_id": {"display_name": "Index ID"},
            "params": {"display_name": "Parameters"},
            "code": {"show": False},
        }

    def build(
        self, api_key: str, client_id: str, index_id: str, params: Optional[dict] = None
    ) -> BaseRetriever:
        try:
            metal = Metal(api_key=api_key, client_id=client_id, index_id=index_id)
        except Exception as e:
            raise ValueError("Could not connect to Metal API.") from e
        return MetalRetriever(client=metal, params=params or {})
