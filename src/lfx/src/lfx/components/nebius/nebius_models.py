from langchain_nebius import ChatNebius
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.base.models.nebius_constants import MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput
from lfx.io import SecretStrInput, SliderInput


class NebiusModelComponent(LCModelComponent):
    display_name = "Nebius Models"
    description = "Generate text using Nebius models."
    documentation = "https://python.langchain.com/docs/integrations/providers/nebius/"
    icon = "Nebius"
    name = "NebiusModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="nebius_api_key",
            display_name="Nebius API Key",
            info="The Nebius API Key to use for the Nebius model.",
            advanced=False,
            required=True,
            value="NEBIUS_API_KEY",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=MODEL_NAMES,
            value=MODEL_NAMES[0],
            refresh_button=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.6,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            info="Controls randomness. Lower values are more deterministic, higher values are more creative.",
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        nebius_api_key = self.nebius_api_key
        temperature = self.temperature
        model_name = self.model_name

        api_key = SecretStr(nebius_api_key).get_secret_value() if nebius_api_key else None

        return ChatNebius(
            model=model_name,
            nebius_api_key=api_key,
            temperature=temperature or 0.6,
        )
