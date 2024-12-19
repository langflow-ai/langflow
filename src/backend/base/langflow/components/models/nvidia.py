from typing import Any

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput
from langflow.schema.dotdict import dotdict


class NVIDIAModelComponent(LCModelComponent):
    display_name = "NVIDIA"
    description = "Generates text using NVIDIA LLMs."
    icon = "NVIDIA"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=["mistralai/mixtral-8x7b-instruct-v0.1"],
            value="mistralai/mixtral-8x7b-instruct-v0.1",
        ),
        StrInput(
            name="base_url",
            display_name="NVIDIA Base URL",
            value="https://integrate.api.nvidia.com/v1",
            refresh_button=True,
            info="The base URL of the NVIDIA API. Defaults to https://integrate.api.nvidia.com/v1.",
        ),
        SecretStrInput(
            name="nvidia_api_key",
            display_name="NVIDIA API Key",
            info="The NVIDIA API Key.",
            advanced=False,
            value="NVIDIA_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "base_url" and field_value:
            try:
                build_model = self.build_model()
                ids = [model.id for model in build_model.available_models]
                build_config["model_name"]["options"] = ids
                build_config["model_name"]["value"] = ids[0]
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
            raise ImportError(msg) from e
        nvidia_api_key = self.nvidia_api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        seed = self.seed
        return ChatNVIDIA(
            max_tokens=max_tokens or None,
            model=model_name,
            base_url=self.base_url,
            api_key=nvidia_api_key,
            temperature=temperature or 0.1,
            seed=seed,
        )
