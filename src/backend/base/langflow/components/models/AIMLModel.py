from langflow.field_typing.range_spec import RangeSpec
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.models.aiml_constants import AIML_CHAT_MODELS
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import (
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    SecretStrInput,
    StrInput,
)


class AIMLModelComponent(LCModelComponent):
    display_name = "AIML"
    description = "Generates text using AIML LLMs."
    icon = "AIML"
    name = "AIMLModel"
    documentation = "https://docs.aimlapi.com/api-reference"

    inputs = LCModelComponent._base_inputs + [
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=AIML_CHAT_MODELS,
            value=AIML_CHAT_MODELS[0],
        ),
        StrInput(
            name="aiml_api_base",
            display_name="AIML API Base",
            advanced=True,
            info="The base URL of the OpenAI API. Defaults to https://api.aimlapi.com . You can change this to use other APIs like JinaChat, LocalAI e Prem.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="AIML API Key",
            info="The AIML API Key to use for the OpenAI model.",
            advanced=False,
            value="AIML_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        aiml_api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs or {}
        aiml_api_base = self.aiml_api_base or "https://api.aimlapi.com"
        seed = self.seed

        if isinstance(aiml_api_key, SecretStr):
            openai_api_key = aiml_api_key.get_secret_value()
        else:
            openai_api_key = aiml_api_key

        model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=openai_api_key,
            base_url=aiml_api_base,
            max_tokens=max_tokens or None,
            seed=seed,
            **model_kwargs,
        )

        return model  # type: ignore

    def _get_exception_message(self, e: Exception):
        """
        Get a message from an OpenAI exception.

        Args:
            exception (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        try:
            from openai.error import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.json_body.get("error", {}).get("message", "")  # type: ignore
            if message:
                return message
        return None
