from langchain_community.chat_models import ChatMaritalk

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput


class MaritalkModelComponent(LCModelComponent):
    display_name = "Maritalk"
    description = "Generates text using Maritalk LLMs."
    icon = "Maritalk"
    name = "Maritalk"
    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            value=512,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            info="Choose between Sabiazinho-3 (smaller and faster) or Sabia-3 (larger and more capable) models.",
            options=["sabiazinho-3", "sabia-3"],
            value=["sabiazinho-3"],
        ),
        SecretStrInput(
            name="api_key",
            display_name="Maritalk API Key",
            info="The Maritalk API Key to use for the OpenAI model.",
            advanced=False,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Run inference with this temperature. Must by in the closed interval [0.0, 0.99].",
            range_spec=RangeSpec(min=0.0, max=0.99, step=0.01),
        ),
    ]

    def build_model(self) -> LanguageModel:
        api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        system_message = self.system_message

        return ChatMaritalk(
            max_tokens=max_tokens,
            model=model_name,
            api_key=api_key,
            temperature=temperature or 0.1,
            system_message=system_message,
        )
