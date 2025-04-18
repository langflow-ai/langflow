import requests

from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, SecretStrInput, SliderInput, StrInput
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

ICOSA_OPTIONS = ["Poll", "Reason (Beta)"]


class IcosaProComponent(Component):
    display_name = "Combinatorial Reasoner"
    description = (
        "Optimize the thinking traces of your models at test-time to increase accuracies. Uses Icosa models if no base URL is given in Controls. Sign up at for a free account at icosacomputing.com."
    )
    icon = "Icosa"
    name = "Combinatorial Reasoner"

    inputs = [
        MessageTextInput(name="prompt", display_name="Prompt", required=True),
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
            advanced=True,
            value=OPENAI_MODEL_NAMES[0],
        ),
        DropdownInput(
            name="prompt_type",
            display_name="Type",
            advanced=False,
            info="(Poll: After sampling N times, gives the most likely answer in Optimized Response. Statistically relevant reasons are given in Selected Reasons. Reason (Beta): Instead of polling, directly uses Selected Reasons to guide the model and get the answer, given in Optimized Response.",
            options=ICOSA_OPTIONS,
            value=ICOSA_OPTIONS[0],
        ),
        SliderInput(
            name="num_samples",
            display_name="Compute Power (Samples)",
            info = "Number of samples to use for the optimization. The more samples, the more accurate the results, but also the more computation is utilized.",
            value=19,
            minLabelIcon="",
            maxLabelIcon="",
            range_spec=RangeSpec(min=10, max=100, step=1),
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="The API Key to use for the OpenAI model.",
            advanced=True,
            value="OPENAI_API_KEY",
            required=False,
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
            display_name="Optimized Response",
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
