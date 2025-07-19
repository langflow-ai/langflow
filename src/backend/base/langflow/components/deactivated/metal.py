# mypy: disable-error-code="attr-defined"
from langchain_community.retrievers import MetalRetriever
from lfx.custom.custom_component.custom_component import CustomComponent

from langflow.base.vectorstores.model import check_cached_vector_store
from langflow.io import DictInput, SecretStrInput, StrInput


class MetalRetrieverComponent(CustomComponent):
    display_name: str = "Metal Retriever"
    description: str = "Retriever that uses the Metal API."
    name = "MetalRetriever"
    legacy = True

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
        ),
        SecretStrInput(
            name="client_id",
            display_name="Client ID",
            required=True,
        ),
        StrInput(
            name="index_id",
            display_name="Index ID",
            required=True,
        ),
        DictInput(
            name="params",
            display_name="Parameters",
            required=False,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> MetalRetriever:
        """Builds the Metal Retriever."""
        try:
            from langchain_community.retrievers import MetalRetriever
            from metal_sdk.metal import Metal
        except ImportError as e:
            msg = "Could not import Metal. Please install it with `pip install metal-sdk langchain-community`."
            raise ImportError(msg) from e

        try:
            metal = Metal(api_key=self.api_key, client_id=self.client_id, index_id=self.index_id)
        except Exception as e:
            msg = "Could not connect to Metal API."
            raise ValueError(msg) from e

        return MetalRetriever(client=metal, params=self.params or {})
