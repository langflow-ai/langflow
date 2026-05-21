from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput

ASTRAFLOW_MODELS = [
    "deepseek-ai/DeepSeek-V3",
    "deepseek-ai/DeepSeek-R1",
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "mistralai/Mistral-Large-Instruct-2411",
    "google/gemma-3-27b-it",
]


class AstraflowComponent(LCModelComponent):
    """Astraflow API component — OpenAI-compatible platform supporting 200+ models by UCloud."""

    display_name = "Astraflow"
    description = "Astraflow by UCloud — OpenAI-compatible platform supporting 200+ models (global endpoint)"
    icon = "Astraflow"
    name = "AstraflowModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Astraflow API key. Sign up at https://astraflow.ucloud-global.com",
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=ASTRAFLOW_MODELS,
            value=ASTRAFLOW_MODELS[0],
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(name="max_tokens", display_name="Max Tokens", advanced=True),
    ]

    def build_model(self) -> LanguageModel:
        """Build the Astraflow model using the OpenAI-compatible endpoint."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": "https://api-us-ca.umodelverse.ai/v1",
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
