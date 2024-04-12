from typing import Any, Dict, List, Optional

from langchain_openai.embeddings.base import OpenAIEmbeddings
from pydantic.v1 import SecretStr

from langflow.field_typing import Embeddings, NestedDict
from langflow.interface.custom.custom_component import CustomComponent


class OpenAIEmbeddingsComponent(CustomComponent):
    display_name = "OpenAI Embeddings"
    description = "Generate embeddings using OpenAI models."

    def build_config(self):
        return {
            "allowed_special": {
                "display_name": "Allowed Special",
                "advanced": True,
                "field_type": "str",
                "is_list": True,
            },
            "default_headers": {
                "display_name": "Default Headers",
                "advanced": True,
                "field_type": "dict",
            },
            "default_query": {
                "display_name": "Default Query",
                "advanced": True,
                "field_type": "NestedDict",
            },
            "disallowed_special": {
                "display_name": "Disallowed Special",
                "advanced": True,
                "field_type": "str",
                "is_list": True,
            },
            "chunk_size": {"display_name": "Chunk Size", "advanced": True},
            "client": {"display_name": "Client", "advanced": True},
            "deployment": {"display_name": "Deployment", "advanced": True},
            "embedding_ctx_length": {
                "display_name": "Embedding Context Length",
                "advanced": True,
            },
            "max_retries": {"display_name": "Max Retries", "advanced": True},
            "model": {
                "display_name": "Model",
                "advanced": False,
                "options": [
                    "text-embedding-3-small",
                    "text-embedding-3-large",
                    "text-embedding-ada-002",
                ],
            },
            "model_kwargs": {"display_name": "Model Kwargs", "advanced": True},
            "openai_api_base": {
                "display_name": "OpenAI API Base",
                "password": True,
                "advanced": True,
            },
            "openai_api_key": {"display_name": "OpenAI API Key", "password": True},
            "openai_api_type": {
                "display_name": "OpenAI API Type",
                "advanced": True,
                "password": True,
            },
            "openai_api_version": {
                "display_name": "OpenAI API Version",
                "advanced": True,
            },
            "openai_organization": {
                "display_name": "OpenAI Organization",
                "advanced": True,
            },
            "openai_proxy": {"display_name": "OpenAI Proxy", "advanced": True},
            "request_timeout": {"display_name": "Request Timeout", "advanced": True},
            "show_progress_bar": {
                "display_name": "Show Progress Bar",
                "advanced": True,
            },
            "skip_empty": {"display_name": "Skip Empty", "advanced": True},
            "tiktoken_model_name": {
                "display_name": "TikToken Model Name",
                "advanced": True,
            },
            "tiktoken_enable": {"display_name": "TikToken Enable", "advanced": True},
        }

    def build(
        self,
        openai_api_key: str,
        default_headers: Optional[Dict[str, str]] = None,
        default_query: Optional[NestedDict] = {},
        allowed_special: List[str] = [],
        disallowed_special: List[str] = ["all"],
        chunk_size: int = 1000,
        client: Optional[Any] = None,
        deployment: str = "text-embedding-ada-002",
        embedding_ctx_length: int = 8191,
        max_retries: int = 6,
        model: str = "text-embedding-ada-002",
        model_kwargs: NestedDict = {},
        openai_api_base: Optional[str] = None,
        openai_api_type: Optional[str] = None,
        openai_api_version: Optional[str] = None,
        openai_organization: Optional[str] = None,
        openai_proxy: Optional[str] = None,
        request_timeout: Optional[float] = None,
        show_progress_bar: bool = False,
        skip_empty: bool = False,
        tiktoken_enable: bool = True,
        tiktoken_model_name: Optional[str] = None,
    ) -> Embeddings:
        # This is to avoid errors with Vector Stores (e.g Chroma)
        if disallowed_special == ["all"]:
            disallowed_special = "all"  # type: ignore
        if openai_api_key:
            api_key = SecretStr(openai_api_key)
        else:
            api_key = None

        return OpenAIEmbeddings(
            tiktoken_enabled=tiktoken_enable,
            default_headers=default_headers,
            default_query=default_query,
            allowed_special=set(allowed_special),
            disallowed_special="all",
            chunk_size=chunk_size,
            client=client,
            deployment=deployment,
            embedding_ctx_length=embedding_ctx_length,
            max_retries=max_retries,
            model=model,
            model_kwargs=model_kwargs,
            base_url=openai_api_base,
            api_key=api_key,
            openai_api_type=openai_api_type,
            api_version=openai_api_version,
            organization=openai_organization,
            openai_proxy=openai_proxy,
            timeout=request_timeout,
            show_progress_bar=show_progress_bar,
            skip_empty=skip_empty,
            tiktoken_model_name=tiktoken_model_name,
        )
