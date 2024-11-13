from langchain_mistralai import ChatMistralAI
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import HandleInput
from langflow.io import BoolInput, DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput


class MistralAIModelComponent(LCModelComponent):
    display_name = "MistralAI"
    description = "Generates text using MistralAI LLMs."
    icon = "MistralAI"
    name = "MistralModel"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=[
                "open-mixtral-8x7b",
                "open-mixtral-8x22b",
                "mistral-small-latest",
                "mistral-medium-latest",
                "mistral-large-latest",
                "codestral-latest",
            ],
            value="codestral-latest",
        ),
        StrInput(
            name="mistral_api_base",
            display_name="Mistral API Base",
            advanced=True,
            info="The base URL of the Mistral API. Defaults to https://api.mistral.ai/v1. "
            "You can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Mistral API Key",
            info="The Mistral API Key to use for the Mistral model.",
            advanced=False,
        ),
        FloatInput(name="temperature", display_name="Temperature", advanced=False, value=0.5),
        IntInput(name="max_retries", display_name="Max Retries", advanced=True, value=5),
        IntInput(name="timeout", display_name="Timeout", advanced=True, value=60),
        IntInput(name="max_concurrent_requests", display_name="Max Concurrent Requests", advanced=True, value=3),
        FloatInput(name="top_p", display_name="Top P", advanced=True, value=1),
        IntInput(name="random_seed", display_name="Random Seed", value=1, advanced=True),
        BoolInput(name="safe_mode", display_name="Safe Mode", advanced=True),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        mistral_api_key = self.api_key
        temperature = self.temperature
        model_name = self.model_name
        max_tokens = self.max_tokens
        mistral_api_base = self.mistral_api_base or "https://api.mistral.ai/v1"
        max_retries = self.max_retries
        timeout = self.timeout
        max_concurrent_requests = self.max_concurrent_requests
        top_p = self.top_p
        random_seed = self.random_seed
        safe_mode = self.safe_mode

        api_key = SecretStr(mistral_api_key).get_secret_value() if mistral_api_key else None

        return ChatMistralAI(
            max_tokens=max_tokens or None,
            model_name=model_name,
            endpoint=mistral_api_base,
            api_key=api_key,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            max_concurrent_requests=max_concurrent_requests,
            top_p=top_p,
            random_seed=random_seed,
            safe_mode=safe_mode,
        )
