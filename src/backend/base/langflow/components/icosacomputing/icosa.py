import requests

from langflow.custom import Component
from langflow.inputs import SecretStrInput
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class IcosaLiteComponent(Component):
    display_name = "Thought Optimizer"
    description = "Optimize the thinking traces of your models at test-time to increase accuracies. Sign up at for a free account at icosacomputing.com."
    icon = "Icosa"
    name = "Icosa"

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
        return prompt

    def build_reasons(self) -> Message:
        # list of selected reasons
        final_reasons = [reason[0] for reason in self.reasons]
        return Message(text="\n".join(final_reasons))
