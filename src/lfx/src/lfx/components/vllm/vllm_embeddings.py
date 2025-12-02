from langchain_openai import OpenAIEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.field_typing import Embeddings
from lfx.io import BoolInput, DictInput, FloatInput, IntInput, MessageTextInput, SecretStrInput


class VllmEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "vLLM Embeddings"
    description = "Generate embeddings using vLLM models via OpenAI-compatible API."
    icon = "vLLM"
    name = "vLLMEmbeddings"

    inputs = [
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            info="The name of the vLLM embeddings model to use (e.g., 'BAAI/bge-large-en-v1.5').",
            value="BAAI/bge-large-en-v1.5",
        ),
        MessageTextInput(
            name="api_base",
            display_name="vLLM API Base",
            advanced=False,
            info="The base URL of the vLLM API server. Defaults to http://localhost:8000/v1 for local vLLM server.",
            value="http://localhost:8000/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API Key to use for the vLLM model (optional for local servers).",
            advanced=False,
            value="",
            required=False,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models.",
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            advanced=True,
            value=1000,
            info="The chunk size to use when processing documents.",
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            value=3,
            advanced=True,
            info="Maximum number of retries for failed requests.",
        ),
        FloatInput(
            name="request_timeout",
            display_name="Request Timeout",
            advanced=True,
            info="Timeout for requests to vLLM API in seconds.",
        ),
        BoolInput(
            name="show_progress_bar",
            display_name="Show Progress Bar",
            advanced=True,
            info="Whether to show a progress bar when processing multiple documents.",
        ),
        BoolInput(
            name="skip_empty",
            display_name="Skip Empty",
            advanced=True,
            info="Whether to skip empty documents.",
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        DictInput(
            name="default_headers",
            display_name="Default Headers",
            advanced=True,
            info="Default headers to use for the API request.",
        ),
        DictInput(
            name="default_query",
            display_name="Default Query",
            advanced=True,
            info="Default query parameters to use for the API request.",
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return OpenAIEmbeddings(
            model=self.model_name,
            base_url=self.api_base or "http://localhost:8000/v1",
            api_key=self.api_key or None,
            dimensions=self.dimensions or None,
            chunk_size=self.chunk_size,
            max_retries=self.max_retries,
            timeout=self.request_timeout or None,
            show_progress_bar=self.show_progress_bar,
            skip_empty=self.skip_empty,
            model_kwargs=self.model_kwargs,
            default_headers=self.default_headers or None,
            default_query=self.default_query or None,
        )
