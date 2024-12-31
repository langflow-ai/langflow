import requests
from requests.auth import HTTPBasicAuth

from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.custom import Component
from langflow.inputs import DropdownInput, SecretStrInput, StrInput
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class CombinatorialReasonerComponent(Component):
    display_name = "Combinatorial Reasoner"
    description = "Uses Combinatorial Optimization to construct an optimal prompt with embedded reasons. Sign up here:\nhttps://forms.gle/oWNv2NKjBNaqqvCx6"
    icon = "Icosa"
    name = "Combinatorial Reasoner"

    inputs = [
        MessageTextInput(name="prompt", display_name="Prompt"),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="The OpenAI API Key to use for the OpenAI model.",
            advanced=False,
            value="OPENAI_API_KEY",
        ),
        StrInput(
            name="username",
            display_name="Username",
            info="Username to authenticate access to Icosa CR API",
            advanced=False,
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            info="Password to authenticate access to Icosa CR API.",
            advanced=False,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=OPENAI_MODEL_NAMES,
            value=OPENAI_MODEL_NAMES[0],
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
        }

        creds = HTTPBasicAuth(self.username, password=self.password)
        response = requests.post(
            "https://cr-api.icosacomputing.com/cr/langflow",
            json=params,
            auth=creds,
            timeout=100,
        )
        response.raise_for_status()

        prompt = response.json()["prompt"]

        self.reasons = response.json()["finalReasons"]
        return prompt

    def build_reasons(self) -> Data:
        # list of selected reasons
        final_reasons = [reason[0] for reason in self.reasons]
        return Data(value=final_reasons)
