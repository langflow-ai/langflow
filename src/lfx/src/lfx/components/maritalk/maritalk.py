from langchain_community.chat_models import ChatMaritalk

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, FloatInput, IntInput, SecretStrInput


class MaritalkModelComponent(LCModelComponent):
    display_name = "Maritalk"
    description = "Generates text using Maritalk LLMs."
    icon = "Maritalk"
    name = "Maritalk"
    inputs = [
        *LCModelComponent.get_base_inputs(),
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
            options=["sabia-2-small", "sabia-2-medium"],
            value=["sabia-2-small"],
        ),
        SecretStrInput(
            name="api_key",
            display_name="Maritalk API Key",
            info="The Maritalk API Key to use for the OpenAI model.",
            advanced=False,
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1, range_spec=RangeSpec(min=0, max=1)),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        # self.output_schea is a list of dictionarie s
        # let's convert it to a dictionary
        api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens

        return ChatMaritalk(
            max_tokens=max_tokens,
            model=model_name,
            api_key=api_key,
            temperature=temperature or 0.1,
        )
