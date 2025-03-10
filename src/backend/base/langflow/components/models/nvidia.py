from typing import Any

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput
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
            options=[],
            refresh_button=True,
            combobox=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="NVIDIA Base URL",
            value="https://integrate.api.nvidia.com/v1",
            refresh_button=True,
            info="The base URL of the NVIDIA API. Defaults to https://integrate.api.nvidia.com/v1.",
            real_time_refresh=True,
        ),
        BoolInput(
            name="tool_model_enabled",
            display_name="Enable Tool Models",
            info=(
                "Select if you want to use models that can work with tools. If yes, only those models will be shown."
            ),
            advanced=False,
            value=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="NVIDIA API Key",
            info="The NVIDIA API Key.",
            advanced=False,
            value="NVIDIA_API_KEY",
            real_time_refresh=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Run inference with this temperature. Must by in the closed interval [0.0, 1.0].",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]

    def get_models(self, tool_model_enabled: bool | None = None) -> list[str]:
        build_model = self.build_model()
        if tool_model_enabled:
            tool_models = [model for model in build_model.get_available_models() if model.supports_tools]
            return [model.id for model in tool_models]
        return [model.id for model in build_model.available_models]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name in {"base_url", "model_name", "tool_model_enabled", "api_key"} and field_value:
            try:
                ids = self.get_models(self.tool_model_enabled)
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
        api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        seed = self.seed
        return ChatNVIDIA(
            max_tokens=max_tokens or None,
            model=model_name,
            base_url=self.base_url,
            api_key=api_key,
            temperature=temperature or 0.1,
            seed=seed,
        )
