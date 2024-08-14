from langchain_community.chat_models import ChatPerplexity
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import FloatInput, SecretStrInput, DropdownInput


class PerplexityComponent(LCModelComponent):
    display_name = "Perplexity"
    description = "Generate text using Perplexity LLMs."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"
    icon = "Google"
    name = "PerplexityModel"

    inputs = LCModelComponent._base_inputs + [
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=['llama-3-sonar-small-32k-online'],
            value="llama-3-sonar-small-32k-online",
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
