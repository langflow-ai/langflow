from typing import cast

from langchain_community.retrievers import MetalRetriever
from metal_sdk.metal import Metal

from langflow.custom import CustomComponent
from langflow.field_typing import Retriever


class MetalRetrieverComponent(CustomComponent):
    display_name: str = "Metal Retriever"
    description: str = "Retriever that uses the Metal API."
    name = "MetalRetriever"
    legacy: bool = True

    def build_config(self):
        return {
            "api_key": {"display_name": "API Key", "password": True},
            "client_id": {"display_name": "Client ID", "password": True},
            "index_id": {"display_name": "Index ID"},
            "params": {"display_name": "Parameters"},
            "code": {"show": False},
        }

    def build(self, api_key: str, client_id: str, index_id: str, params: dict | None = None) -> Retriever:  # type: ignore[type-var]
        try:
            metal = Metal(api_key=api_key, client_id=client_id, index_id=index_id)
        except Exception as e:
            msg = "Could not connect to Metal API."
            raise ValueError(msg) from e
        return cast("Retriever", MetalRetriever(client=metal, params=params or {}))
