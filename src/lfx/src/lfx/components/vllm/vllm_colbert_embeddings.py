from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.components.vllm.colbert_embeddings_impl import VllmColBERTEmbeddings

if TYPE_CHECKING:
    from lfx.field_typing import Embeddings
from lfx.io import FloatInput, IntInput, MessageTextInput, SecretStrInput


class VllmColBERTEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "vLLM ColBERT Embeddings"
    description = (
        "Multi-vector (ColBERT-style) token embeddings via vLLM. "
        "Returns one token matrix per document — compatible with NextPlaid."
    )
    icon = "vLLM"
    name = "VllmColBERTEmbeddings"

    inputs = [
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            info="ColBERT-compatible model served by vLLM, e.g. 'answerdotai/answerai-colbert-small-v1'.",
            value="answerdotai/answerai-colbert-small-v1",
        ),
        MessageTextInput(
            name="api_base",
            display_name="vLLM API Base",
            advanced=False,
            info="Base URL of the vLLM server. Do NOT include /v1 — added automatically.",
            value="http://localhost:8000",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for the vLLM server. Leave empty for local servers.",
            advanced=False,
            value="",
            required=False,
        ),
        FloatInput(
            name="request_timeout",
            display_name="Request Timeout",
            advanced=True,
            value=60.0,
            info="Timeout in seconds for requests to the vLLM API.",
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            advanced=True,
            value=3,
            info="Number of times to retry a failed request before raising an error.",
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return VllmColBERTEmbeddings(
            url=self.api_base or "http://localhost:8000",
            model=self.model_name,
            api_key=self.api_key or "",
            timeout=self.request_timeout or 60.0,
            max_retries=self.max_retries or 1,
        )
