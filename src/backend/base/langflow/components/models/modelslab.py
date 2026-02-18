"""
ModelsLab LLM component for Langflow.

Provides uncensored Llama 3.1 8B and 70B models via ModelsLab's
OpenAI-compatible API endpoint.

Get your API key at: https://modelslab.com
API docs: https://docs.modelslab.com/uncensored-chat
"""

from langchain_openai import ChatOpenAI
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    SliderInput,
)

MODELSLAB_CHAT_MODELS = [
    "llama-3.1-8b-uncensored",
    "llama-3.1-70b-uncensored",
]

MODELSLAB_CHAT_BASE_URL = "https://modelslab.com/uncensored-chat/v1"


class ModelsLabModelComponent(LCModelComponent):
    """
    ModelsLab LLM component for Langflow.

    Connects to ModelsLab's OpenAI-compatible endpoint to provide uncensored
    Llama 3.1 models with 128K token context windows.
    """

    display_name: str = "ModelsLab"
    description: str = (
        "Chat with ModelsLab's uncensored Llama 3.1 models (8B & 70B) via an "
        "OpenAI-compatible API. Ideal for creative writing, research, and use cases "
        "where standard content restrictions are too limiting. 128K context window."
    )
    documentation: str = "https://docs.modelslab.com/uncensored-chat"
    icon: str = "ModelsLab"
    name: str = "ModelsLabModel"

    inputs = [
        *LCModelComponent._base_inputs,
        SecretStrInput(
            name="api_key",
            display_name="ModelsLab API Key",
            info="Your ModelsLab API key. Get one at https://modelslab.com",
            real_time_refresh=True,
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The ModelsLab model to use for generation.",
            options=MODELSLAB_CHAT_MODELS,
            value=MODELSLAB_CHAT_MODELS[0],
            refresh_button=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness. Lower = more deterministic, higher = more creative.",
            value=0.7,
            range_spec={"min": 0.0, "max": 2.0, "step": 0.1},
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate. Leave at 0 for model default.",
            value=0,
            advanced=True,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="Nucleus sampling probability. 1.0 = no filtering.",
            value=1.0,
            advanced=True,
        ),
        IntInput(
            name="n",
            display_name="Number of Completions",
            info="How many completions to generate per prompt.",
            value=1,
            advanced=True,
        ),
        BoolInput(
            name="stream",
            display_name="Stream",
            info="Stream the response token by token.",
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="ModelsLab API base URL. Override only if using a custom endpoint.",
            value=MODELSLAB_CHAT_BASE_URL,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Text",
            name="text_output",
            method="text_response",
        ),
        Output(
            display_name="Language Model",
            name="model_output",
            method="build_model",
        ),
    ]

    def build_model(self) -> LanguageModel:
        """
        Instantiate and return a ChatOpenAI model configured for ModelsLab.
        """
        if not self.api_key:
            msg = (
                "ModelsLab API key is required. "
                "Get yours at https://modelslab.com"
            )
            raise ValueError(msg)

        params: dict = {
            "model": self.model_name,
            "openai_api_key": self.api_key,
            "openai_api_base": self.base_url or MODELSLAB_CHAT_BASE_URL,
            "temperature": self.temperature,
            "streaming": self.stream,
            "n": self.n,
            "top_p": self.top_p,
        }

        if self.max_tokens and self.max_tokens > 0:
            params["max_tokens"] = self.max_tokens

        return ChatOpenAI(**params)
