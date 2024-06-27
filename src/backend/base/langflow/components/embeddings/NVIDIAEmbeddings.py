from typing import Any

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.io import FloatInput, MessageTextInput
from langflow.schema.dotdict import dotdict


class NVIDIAEmbeddingsComponent(LCEmbeddingsModel):
    display_name: str = "NVIDIA Embeddings"
    description: str = "Generate embeddings using NVIDIA models."
    icon = "NVIDIA"

    inputs = [
        MessageTextInput(
            name="model",
            display_name="Model",
        ),
        MessageTextInput(
            name="base_url",
            display_name="NVIDIA Base URL",
            refresh_button=True,
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
                raise ValueError(f"Error getting model names: {e}")
        return build_config

    def build_embeddings(self) -> Embeddings:
        try:
            from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
        except ImportError:
            raise ImportError("Please install langchain-nvidia-ai-endpoints to use the Nvidia model.")
        try:
            output = NVIDIAEmbeddings(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to Ollama API.") from e
        return output
