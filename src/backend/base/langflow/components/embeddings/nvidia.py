from typing import Any

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.inputs.inputs import DropdownInput, SecretStrInput
from langflow.io import FloatInput, MessageTextInput
from langflow.schema.dotdict import dotdict


class NVIDIAEmbeddingsComponent(LCEmbeddingsModel):
    display_name: str = "NVIDIA Embeddings"
    description: str = "Generate embeddings using NVIDIA models."
    icon = "NVIDIA"

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            options=[
                "nvidia/nv-embed-v1",
                "snowflake/arctic-embed-I",
            ],
            value="nvidia/nv-embed-v1",
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="NVIDIA Base URL",
            refresh_button=True,
            value="https://integrate.api.nvidia.com/v1",
            required=True,
        ),
        SecretStrInput(
            name="nvidia_api_key",
            display_name="NVIDIA API Key",
            info="The NVIDIA API Key.",
            advanced=False,
            value="NVIDIA_API_KEY",
            required=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Model Temperature",
            value=0.1,
            advanced=True,
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "base_url" and field_value:
            try:
                build_model = self.build_embeddings()
                ids = [model.id for model in build_model.available_models]
                build_config["model"]["options"] = ids
                build_config["model"]["value"] = ids[0]
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_embeddings(self) -> Embeddings:
        try:
            from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the Nvidia model."
            raise ImportError(msg) from e
        try:
            output = NVIDIAEmbeddings(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
                nvidia_api_key=self.nvidia_api_key,
            )
        except Exception as e:
            msg = f"Could not connect to NVIDIA API. Error: {e}"
            raise ValueError(msg) from e
        return output
