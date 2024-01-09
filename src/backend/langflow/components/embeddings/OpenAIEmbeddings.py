
from langflow import CustomComponent
from typing import Optional, Set, Dict, Any, Union, Callable
from langchain.embeddings import OpenAIEmbeddings

class OpenAIEmbeddingsComponent(CustomComponent):
    display_name = "OpenAIEmbeddings"
    description = "OpenAI embedding models"

    def build_config(self):
        return {
            "allowed_special": {"display_name": "Allowed Special", "advanced": True},
            "disallowed_special": {"display_name": "Disallowed Special", "advanced": True},
            "chunk_size": {"display_name": "Chunk Size", "advanced": True},
            "client": {"display_name": "Client", "advanced": True},
            "deployment": {"display_name": "Deployment", "advanced": True},
            "embedding_ctx_length": {"display_name": "Embedding Context Length", "advanced": True},
            "max_retries": {"display_name": "Max Retries", "advanced": True},
            "model": {"display_name": "Model", "advanced": True},
            "model_kwargs": {"display_name": "Model Kwargs", "advanced": True},
            "openai_api_base": {"display_name": "OpenAI API Base", "advanced": True},
            "openai_api_key": {"display_name": "OpenAI API Key"},
            "openai_api_type": {"display_name": "OpenAI API Type", "advanced": True},
            "openai_api_version": {"display_name": "OpenAI API Version", "advanced": True},
            "openai_organization": {"display_name": "OpenAI Organization", "advanced": True},
            "openai_proxy": {"display_name": "OpenAI Proxy", "advanced": True},
            "request_timeout": {"display_name": "Request Timeout", "advanced": True},
            "show_progress_bar": {"display_name": "Show Progress Bar", "advanced": True},
            "skip_empty": {"display_name": "Skip Empty", "advanced": True},
            "tiktoken_model_name": {"display_name": "TikToken Model Name"},
        }

    def build(
        self,
        allowed_special: Optional[Set[str]] = set(),
        disallowed_special: str = "all",
        chunk_size: Optional[int] = 1000,
        client: Optional[Any] = None,
        deployment: str = "text-embedding-ada-002",
        embedding_ctx_length: Optional[int] = 8191,
        max_retries: Optional[int] = 6,
        model: str = "text-embedding-ada-002",
        model_kwargs: Optional[Dict[str, Any]] = None,
        openai_api_base: Optional[str] = None,
        openai_api_key: Optional[str] = '',
        openai_api_type: Optional[str] = None,
        openai_api_version: Optional[str] = None,
        openai_organization: Optional[str] = None,
        openai_proxy: Optional[str] = None,
        request_timeout: Optional[float] = None,
        show_progress_bar: Optional[bool] = False,
        skip_empty: Optional[bool] = False,
        tiktoken_model_name: Optional[str] = None,
    ) -> Union[OpenAIEmbeddings, Callable]:
        return OpenAIEmbeddings(
            allowed_special=allowed_special,
            disallowed_special=disallowed_special,
            chunk_size=chunk_size,
            client=client,
            deployment=deployment,
            embedding_ctx_length=embedding_ctx_length,
            max_retries=max_retries,
            model=model,
            model_kwargs=model_kwargs,
            openai_api_base=openai_api_base,
            openai_api_key=openai_api_key,
            openai_api_type=openai_api_type,
            openai_api_version=openai_api_version,
            openai_organization=openai_organization,
            openai_proxy=openai_proxy,
            request_timeout=request_timeout,
            show_progress_bar=show_progress_bar,
            skip_empty=skip_empty,
            tiktoken_model_name=tiktoken_model_name,
        )
