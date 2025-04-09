import requests

from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, SecretStrInput, SliderInput, StrInput
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

ICOSA_OPTIONS = ["Consensus", "CR", "CR w/ consensus"]


class IcosaProComponent(Component):
    display_name = "Icosa Pro"
    description = (
        "Uses inference-time compute to construct an optimized prompt."
        "Makes multiple calls to LLM chosen. Sign up at icosacomputing.com"
    )
    icon = "Icosa"
    name = "Icosa Pro"

    inputs = [
        MessageTextInput(name="prompt", display_name="Prompt", required=True),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="The API Key to use for the OpenAI model.",
            advanced=False,
            value="OPENAI_API_KEY",
            required=False,
        ),
        SecretStrInput(
            name="icosa_api_key",
            display_name="Icosa API Key",
            info="Sign up at icosacomputing.com for this key",
            advanced=False,
            value="ICOSA_API_KEY",
            required=True,
        ),
        StrInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            value=OPENAI_MODEL_NAMES[0],
        ),
        DropdownInput(
            name="prompt_type",
            display_name="Type",
            advanced=False,
            options=ICOSA_OPTIONS,
            value=ICOSA_OPTIONS[0],
        ),
        SliderInput(
            name="num_samples",
            display_name="Compute Cost",
            value=50,
            range_spec=RangeSpec(min=10, max=200, step=1),
        ),
        StrInput(
            name="base_url",
            display_name="Base URL",
            info="Call any provider compatible with OpenAI's SDK by providing a base URL",
            advanced=True,
            value="",
        ),
    ]

    outputs = [
        Output(
            display_name="Optimized Prompt",
            name="optimized_prompt",
            method="build_prompt",
        ),
        Output(display_name="Selected Reasons", name="reasons", method="build_reasons"),
    ]

    def build_prompt(self) -> Message:
        params = {
            "prompt": self.prompt,
            "apiKey": self.openai_api_key,
            "model": self.model_name,
            "type": self.prompt_type,
            "numSamples": self.num_samples,
            "baseUrl": self.base_url,
        }
        headers = {"X-API-Key": self.icosa_api_key}
        response = requests.post(
            "https://cr-api.icosacomputing.com/cr/langflow_pro",
            json=params,
            headers=headers,
            timeout=100,
        )
        response.raise_for_status()

        prompt = response.json()["prompt"]

        self.reasons = response.json()["finalReasons"]
        return prompt

    def build_reasons(self) -> Message:
        # list of selected reasons
        final_reasons = [reason[0] for reason in self.reasons]
        return Message(text="\n".join(final_reasons))
