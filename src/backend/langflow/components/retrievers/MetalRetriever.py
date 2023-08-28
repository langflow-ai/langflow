from typing import Optional
from langflow import CustomComponent
from langchain.retrievers import MetalRetriever
from langchain.schema.retriever import BaseRetriever


class MetalRetrieverComponent(CustomComponent):
    display_name: str = "Metal Retriever"
    description: str = "Retriever that uses the Metal API."

    def build_config(self):
        return {
            "api_key": {"display_name": "API Key", "password": True},
            "client_id": {"display_name": "Client ID", "password": True},
            "index_id": {"display_name": "Index ID"},
            "params": {"display_name": "Parameters", "field_type": "code"},
            "code": {"show": False},
        }

    def build(
        self, api_key: str, client_id: str, index_id: str, params: Optional[dict] = None
    ) -> BaseRetriever:
        return MetalRetriever(api_key, client_id, index_id, params=params)
