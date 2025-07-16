from langchain_community.chat_models import ChatPerplexity
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DropdownInput, FloatInput, SecretStrInput, SliderInput
from langflow.logging import logger


class PerplexityComponent(LCModelComponent):
    display_name = "Perplexity"
    description = "Generate text using Perplexity LLMs."
    documentation = "https://python.langchain.com/docs/integrations/chat/perplexity/"
    icon = "Perplexity"
    name = "PerplexityModel"

    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            required=True,
            options=[
                "sonar",
                "sonar-pro",
                "sonar-reasoning",
                "sonar-reasoning-pro",
                "sonar-deep-research",
            ],
            value="sonar",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Perplexity API Key",
            info="The Perplexity API Key to use for the Perplexity model.",
            advanced=False,
            required=True,
        ),
        SliderInput(
            name="temperature", display_name="Temperature", value=0.75, range_spec=RangeSpec(min=0, max=2, step=0.05)
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="The maximum cumulative probability of tokens to consider when sampling.",
            value=0.9,
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        logger.debug(f"Executing request with model: {self.model_name}")
        api_key = SecretStr(self.api_key).get_secret_value()
        temperature = self.temperature
        model = self.model_name
        top_p = self.top_p

        return ChatPerplexity(
            model=model,
            temperature=temperature or 0.75,
            pplx_api_key=api_key,
            top_p=top_p or None,
        )
