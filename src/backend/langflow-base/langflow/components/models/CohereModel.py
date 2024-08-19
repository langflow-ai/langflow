from langchain_cohere import ChatCohere
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import FloatInput, SecretStrInput


class CohereComponent(LCModelComponent):
    display_name = "Cohere"
    description = "Generate text using Cohere LLMs."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"
    icon = "Cohere"
    name = "CohereModel"

    inputs = LCModelComponent._base_inputs + [
        SecretStrInput(
            name="cohere_api_key",
            display_name="Cohere API Key",
            info="The Cohere API Key to use for the Cohere model.",
            advanced=False,
            value="COHERE_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.75),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        cohere_api_key = self.cohere_api_key
        temperature = self.temperature

        if cohere_api_key:
            api_key = SecretStr(cohere_api_key)
        else:
            api_key = None

        output = ChatCohere(
            temperature=temperature or 0.75,
            cohere_api_key=api_key,
        )

        return output  # type: ignore
