from __future__ import annotations

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.components.vllm.vllm_multivector_impl import VllmMultivectorEmbeddings
from lfx.field_typing import Embeddings  # noqa: TC001
from lfx.io import FloatInput, IntInput, MessageTextInput, SecretStrInput


class VllmMultivectorEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "vLLM Multivector Embeddings"
    description = (
        "Multi-vector (ColBERT/ColPali-style) token embeddings via vLLM's /pooling endpoint. "
        "Compatible with text-only ColBERT models and multi-modal ColPali models. "
        "Required for use with the NextPlaid vector store."
    )
    icon = "vLLM"
    name = "VllmMultivectorEmbeddings"

    inputs = [
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            info=(
                "Multi-vector model served by vLLM. Examples:\n"
                "Text (ColBERT): answerdotai/answerai-colbert-small-v1\n"
                "Text + Images (ColPali): ModernVBERT/colmodernvbert"
            ),
            value="answerdotai/answerai-colbert-small-v1",
        ),
        MessageTextInput(
            name="api_base",
            display_name="vLLM API Base",
            advanced=False,
            info=(
                "Base URL of the vLLM server (no /v1 suffix). "
                "Start vLLM with: vllm serve <model> --runner pooling "
                '--pooler-config \'{"task": "token_embed"}\''
            ),
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
            info="Timeout in seconds for each request to the vLLM API.",
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
        return VllmMultivectorEmbeddings(
            url=self.api_base or "http://localhost:8000",
            model=self.model_name,
            api_key=self.api_key or "",
            timeout=self.request_timeout or 60.0,
            max_retries=self.max_retries or 1,
        )
