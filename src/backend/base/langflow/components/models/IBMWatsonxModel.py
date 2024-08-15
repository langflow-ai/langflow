from pydantic.v1 import SecretStr

from langchain_ibm import ChatWatsonx

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import DropdownInput, FloatInput, IntInput, SecretStrInput, MessageTextInput


class IBMWatsonXComponent(LCModelComponent):
    display_name = "IBM watsonx"
    description = "Generate text using IBM watsonx."
    icon = "IBM"
    name = "IBMwatsonxModel"
    inputs = LCModelComponent._base_inputs + [
        DropdownInput(
            name="model",
            display_name="Model",
            info="The name of the model to use.",
            options=["ibm/granite-13b-chat-v2"],
            value="ibm/granite-13b-chat-v2",
        ),
        DropdownInput(
            name="url",
            display_name="URL",
            info="https://ibm.github.io/watsonx-ai-python-sdk/setup_cloud.html#authentication.",
            options=[
                "https://us-south.ml.cloud.ibm.com",
                "https://eu-gb.ml.cloud.ibm.com",
                "https://eu-de.ml.cloud.ibm.com",
                "https://jp-tok.ml.cloud.ibm.com",
            ],
            value="https://us-south.ml.cloud.ibm.com",
        ),
        MessageTextInput(
            name="project_id",
            display_name="Project_ID",
            info="https://www.ibm.com/docs/en/watsonx-as-a-service?topic=projects.",
        ),
        SecretStrInput(
            name="watsonx_api_key",
            display_name="Watsonx API Key",
            info="The Watson API Key to use for Watsonx.",
        ),
        IntInput(
            name="max_output_tokens",
            display_name="Max Output Tokens",
            info="The maximum number of tokens to generate.",
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="The maximum cumulative probability of tokens to consider when sampling.",
            advanced=True,
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.",
            advanced=True,
        ),
    ]

    def build_output(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = SecretStr(self.watsonx_api_key).get_secret_value()
        model = self.model
        project_id = self.project_id
        url = self.url
        max_output_tokens = self.max_output_tokens
        temperature = self.temperature
        top_k = self.top_k
        top_p = self.top_p
        # n = self.n
        try:
            output = ChatWatsonx(
                model_id=model,
                url=url,
                project_id=project_id,
                apikey=api_key,
                max_output_tokens=max_output_tokens or None,
                temperature=temperature or 0.1,
                top_k=top_k or None,
                top_p=top_p or None,
            )
        except Exception as e:
            raise ValueError("Could not connect to IBM API.") from e

        return output
