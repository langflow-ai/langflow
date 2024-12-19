from langchain_community.chat_models.sambanova import ChatSambaNovaCloud
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.base.models.sambanova_constants import SAMBANOVA_MODEL_NAMES
from langflow.field_typing import LanguageModel
from langflow.io import DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput


class SambaNovaComponent(LCModelComponent):
    display_name = "SambaNova"
    description = "Generate text using Sambanova LLMs."
    documentation = "https://cloud.sambanova.ai/"
    icon = "SambaNova"
    name = "SambaNovaModel"

    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(
            name="sambanova_url",
            display_name="SambaNova Cloud Base Url",
            advanced=True,
            info="The base URL of the Sambanova Cloud API. "
            "Defaults to https://api.sambanova.ai/v1/chat/completions. "
            "You can change this to use other urls like Sambastudio",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=SAMBANOVA_MODEL_NAMES,
            value=SAMBANOVA_MODEL_NAMES[0],
        ),
        SecretStrInput(
            name="sambanova_api_key",
            display_name="Sambanova API Key",
            info="The Sambanova API Key to use for the Sambanova model.",
            advanced=False,
            value="SAMBANOVA_API_KEY",
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            value=4096,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.07),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        sambanova_url = self.sambanova_url
        sambanova_api_key = self.sambanova_api_key
        model_name = self.model_name
        max_tokens = self.max_tokens
        temperature = self.temperature

        api_key = SecretStr(sambanova_api_key).get_secret_value() if sambanova_api_key else None

        return ChatSambaNovaCloud(
            model=model_name,
            max_tokens=max_tokens or 1024,
            temperature=temperature or 0.07,
            sambanova_url=sambanova_url,
            sambanova_api_key=api_key,
        )
