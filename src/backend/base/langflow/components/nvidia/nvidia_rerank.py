from typing import Any

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.field_typing import VectorStore
from langflow.inputs.inputs import DataInput
from langflow.io import DropdownInput, MultilineInput, SecretStrInput, StrInput
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
            tool_mode=True,
        ),
        StrInput(
            name="base_url",
            display_name="Base URL",
            value="https://integrate.api.nvidia.com/v1",
            refresh_button=True,
            info="The base URL of the NVIDIA API. Defaults to https://integrate.api.nvidia.com/v1.",
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["nv-rerank-qa-mistral-4b:1"],
            value="nv-rerank-qa-mistral-4b:1",
        ),
        SecretStrInput(name="api_key", display_name="API Key"),
        DataInput(
            name="search_results",
            display_name="Search Results",
            info="Search Results from a Vector Store.",
            is_list=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Reranked Documents",
            name="reranked_documents",
            method="rerank_documents",
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
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_reranker(self):
        try:
            from langchain_nvidia_ai_endpoints import NVIDIARerank
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
            raise ImportError(msg) from e
        return NVIDIARerank(api_key=self.api_key, model=self.model, base_url=self.base_url)

    async def rerank_documents(self) -> list[Data]:  # type: ignore[override]
        reranker = self.build_reranker()
        documents = reranker.compress_documents(
            query=self.search_query,
            documents=[passage.to_lc_document() for passage in self.search_results if isinstance(passage, Data)],
        )
        data = self.to_data(documents)
        self.status = data
        return data

    @check_cached_vector_store
    def build_vector_store(self) -> VectorStore:
        msg = "NVIDIA Rerank does not support vector stores."
        raise NotImplementedError(msg)
