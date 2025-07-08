from langchain_cohere import ChatCohere
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import SecretStrInput, SliderInput


class CohereComponent(LCModelComponent):
    display_name = "Cohere Language Models"
    description = "Generate text using Cohere LLMs."
    documentation = "https://python.langchain.com/docs/modules/model_io/models/llms/integrations/cohere"
    icon = "Cohere"
    name = "CohereModel"

    inputs = [
        *LCModelComponent._base_inputs,
        SecretStrInput(
            name="cohere_api_key",
            display_name="Cohere API Key",
            info="The Cohere API Key to use for the Cohere model.",
            advanced=False,
            value="COHERE_API_KEY",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.75,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            info="Controls randomness. Lower values are more deterministic, higher values are more creative.",
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        cohere_api_key = self.cohere_api_key
        temperature = self.temperature

        api_key = SecretStr(cohere_api_key).get_secret_value() if cohere_api_key else None

        return ChatCohere(
            temperature=temperature or 0.75,
            cohere_api_key=api_key,
        )
