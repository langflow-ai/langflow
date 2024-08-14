from langchain_community.chat_models import ChatPerplexity
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import FloatInput, SecretStrInput, DropdownInput

PERPLEXITY_MODEL_NAMES = [
    "llama-3.1-sonar-small-128k-online",
    "llama-3.1-sonar-large-128k-online",
    "llama-3.1-sonar-huge-128k-online",
    "llama-3.1-sonar-small-128k-chat",
    "llama-3.1-sonar-large-128k-chat",
    "llama-3.1-8b-instruct",
    "llama-3.1-70b-instruct",
]

class PerplexityComponent(LCModelComponent):
    display_name = "Perplexity"
    description = "Generate text using Perplexity LLMs."
    documentation = "https://python.langchain.com/v0.2/docs/integrations/chat/perplexity/"
    icon = "Perplexity"
    name = "PerplexityModel"

    inputs = LCModelComponent._base_inputs + [
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=PERPLEXITY_MODEL_NAMES,
            value=PERPLEXITY_MODEL_NAMES[0],
        ),
        SecretStrInput(
            name="api_key",
            display_name="Perplexity API Key",
            info="The Perplexity API Key to use for the Perplexity model.",
            advanced=False,
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.75),

    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = SecretStr(self.api_key).get_secret_value()
        temperature = self.temperature
        model = self.model_name


        output = ChatPerplexity(
            model=model,
            temperature=temperature or 0.75,
            pplx_api_key=api_key,
        )

        return output  # type: ignore
