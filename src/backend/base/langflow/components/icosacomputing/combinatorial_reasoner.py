import requests

from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, SecretStrInput, SliderInput, StrInput
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

ICOSA_OPTIONS = ["Poll", "Reason (Beta)"]


class CombinatorialReasonerComponent(Component):
    display_name = "Combinatorial Reasoner"
    description = (
        "Optimize the “thinking” of models at test-time to increase accuracy. Uses Icosa models by default "
        "but can run on any model by changing base URL in Controls. Sign up for free at icosacomputing.com. "
        "Get the Response directly, or use the Optimized Prompt to a model of your choice."
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
            info=(
                "(Poll: After sampling N times, gives the most likely answer in Optimized Response. "
                "Statistically relevant reasons are given in Selected Reasons. Reason (Beta): Instead of "
                "polling, directly uses Selected Reasons to guide the model and get the answer, given in "
                "Optimized Response."
            ),
            options=ICOSA_OPTIONS,
            value=ICOSA_OPTIONS[0],
        ),
        SliderInput(
            name="num_samples",
            display_name="Compute Power (Samples)",
            info=(
                "Number of samples to use for the optimization. More samples implies more accurate results, "
                "but increased compute."
            ),
            min_label="",
            max_label="",
            value=15,
            range_spec=RangeSpec(min=1, max=30, step=1, step_type="int"),
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
            display_name="Optimized Prompt",
            name="optimized_prompt",
            method="build_prompt",
        ),
        Output(
            display_name="Response",
            name="response",
            method="build_response",
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
            "https://cr-api.icosacomputing.com/cr/langflow_lite",
            json=params,
            headers=headers,
            timeout=100,
        )
        response.raise_for_status()

        prompt = response.json()["prompt"]
        self.reasons = response.json()["finalReasons"]
        self.response = response.json()["answerWithReasoning"]
        return prompt

    def build_response(self) -> Message:
        return self.response

    def build_reasons(self) -> Message:
        final_reasons = [reason[0] for reason in self.reasons]
        return Message(text="\n".join(final_reasons))
