from typing import Any

from lfx.base.compressors.model import LCCompressorComponent
from lfx.field_typing import BaseDocumentCompressor
from lfx.inputs.inputs import SecretStrInput
from lfx.io import DropdownInput, StrInput
from lfx.schema.dotdict import dotdict
from lfx.template.field.base import Output


class NvidiaRerankComponent(LCCompressorComponent):
    display_name = "NVIDIA Rerank"
    description = "Rerank documents using the NVIDIA API."
    icon = "NVIDIA"

    inputs = [
        *LCCompressorComponent.inputs,
        SecretStrInput(
            name="api_key",
            display_name="NVIDIA API Key",
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
    ]

    outputs = [
        Output(
            display_name="Reranked Documents",
            name="reranked_documents",
            method="compress_documents",
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "base_url" and field_value:
            try:
                build_model = self.build_compressor()
                ids = [model.id for model in build_model.available_models]
                build_config["model"]["options"] = ids
                build_config["model"]["value"] = ids[0]
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_compressor(self) -> BaseDocumentCompressor:
        try:
            from langchain_nvidia_ai_endpoints import NVIDIARerank
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
            raise ImportError(msg) from e
        return NVIDIARerank(api_key=self.api_key, model=self.model, base_url=self.base_url, top_n=self.top_n)
