from typing import Any, List, cast

from langchain.retrievers import ContextualCompressionRetriever

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.field_typing import Retriever, VectorStore
from langflow.io import DropdownInput, HandleInput, MultilineInput, SecretStrInput, StrInput
from langflow.schema import Data
from langflow.schema.dotdict import dotdict
from langflow.template.field.base import Output


class NvidiaRerankComponent(LCVectorStoreComponent):
    display_name = "NVIDIA Rerank"
    description = "Rerank documents using the NVIDIA API and a retriever."
    icon = "NVIDIA"

    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
        ),
        StrInput(
            name="base_url",
            display_name="Base URL",
            value="https://integrate.api.nvidia.com/v1",
            refresh_button=True,
            info="The base URL of the NVIDIA API. Defaults to https://integrate.api.nvidia.com/v1.",
        ),
        DropdownInput(
            name="model", display_name="Model", options=["nv-rerank-qa-mistral-4b:1"], value="nv-rerank-qa-mistral-4b:1"
        ),
        SecretStrInput(name="api_key", display_name="API Key"),
        HandleInput(name="retriever", display_name="Retriever", input_types=["Retriever"]),
    ]

    outputs = [
        Output(
            display_name="Retriever",
            name="base_retriever",
            method="build_base_retriever",
        ),
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "base_url" and field_value:
            try:
                build_model = self.build_model()
                ids = [model.id for model in build_model.available_models]
                build_config["model"]["options"] = ids
                build_config["model"]["value"] = ids[0]
            except Exception as e:
                raise ValueError(f"Error getting model names: {e}")
        return build_config

    def build_model(self):
        try:
            from langchain_nvidia_ai_endpoints import NVIDIARerank
        except ImportError:
            raise ImportError("Please install langchain-nvidia-ai-endpoints to use the NVIDIA model.")
        return NVIDIARerank(api_key=self.api_key, model=self.model, base_url=self.base_url)

    def build_base_retriever(self) -> Retriever:  # type: ignore[type-var]
        nvidia_reranker = self.build_model()
        retriever = ContextualCompressionRetriever(base_compressor=nvidia_reranker, base_retriever=self.retriever)
        return cast(Retriever, retriever)

    async def search_documents(self) -> List[Data]:  # type: ignore
        retriever = self.build_base_retriever()
        documents = await retriever.ainvoke(self.search_query, config={"callbacks": self.get_langchain_callbacks()})
        data = self.to_data(documents)
        self.status = data
        return data

    def build_vector_store(self) -> VectorStore:
        raise NotImplementedError("NVIDIA Rerank does not support vector stores.")
