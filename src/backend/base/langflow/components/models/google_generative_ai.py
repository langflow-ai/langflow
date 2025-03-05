from typing import Any

import requests
from loguru import logger
from pydantic.v1 import SecretStr

from langflow.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, FloatInput, IntInput, SecretStrInput, SliderInput
from langflow.inputs.inputs import BoolInput
from langflow.schema import dotdict


class GoogleGenerativeAIComponent(LCModelComponent):
    display_name = "Google Generative AI"
    description = "Generate text using Google Generative AI."
    icon = "GoogleGenerativeAI"
    name = "GoogleGenerativeAIModel"

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_output_tokens", display_name="Max Output Tokens", info="The maximum number of tokens to generate."
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The name of the model to use.",
            options=GOOGLE_GENERATIVE_AI_MODELS,
            value="gemini-1.5-pro",
            refresh_button=True,
            combobox=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Google API Key",
            info="The Google API Key to use for the Google Generative AI.",
            required=True,
            real_time_refresh=True,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="The maximum cumulative probability of tokens to consider when sampling.",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            info="Controls randomness. Lower values are more deterministic, higher values are more creative.",
        ),
        IntInput(
            name="n",
            display_name="N",
            info="Number of chat completions to generate for each prompt. "
            "Note that the API may not return the full n completions if duplicates are generated.",
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.",
            advanced=True,
        ),
        BoolInput(
            name="tool_model_enabled",
            display_name="Tool Model Enabled",
            info="Whether to use the tool model.",
            value=False,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            msg = "The 'langchain_google_genai' package is required to use the Google Generative AI model."
            raise ImportError(msg) from e

        google_api_key = self.api_key
        model = self.model_name
        max_output_tokens = self.max_output_tokens
        temperature = self.temperature
        top_k = self.top_k
        top_p = self.top_p
        n = self.n

        return ChatGoogleGenerativeAI(
            model=model,
            max_output_tokens=max_output_tokens or None,
            temperature=temperature,
            top_k=top_k or None,
            top_p=top_p or None,
            n=n or 1,
            google_api_key=SecretStr(google_api_key).get_secret_value(),
        )

    def get_models(self, tool_model_enabled: bool | None = None) -> list[str]:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model_ids = [
                model.name.replace("models/", "")
                for model in genai.list_models()
                if "generateContent" in model.supported_generation_methods
            ]
            model_ids.sort(reverse=True)
        except (ImportError, ValueError) as e:
            logger.exception(f"Error getting model names: {e}")
            model_ids = GOOGLE_GENERATIVE_AI_MODELS
        if tool_model_enabled:
            try:
                from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
            except ImportError as e:
                msg = "langchain_google_genai is not installed."
                raise ImportError(msg) from e
            for model in model_ids:
                model_with_tool = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.api_key,
                )
                if not self.supports_tool_calling(model_with_tool):
                    model_ids.remove(model)
        return model_ids

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name in {"base_url", "model_name", "tool_model_enabled", "api_key"} and field_value:
            try:
                if len(self.api_key) == 0:
                    ids = GOOGLE_GENERATIVE_AI_MODELS
                else:
                    try:
                        ids = self.get_models(tool_model_enabled=self.tool_model_enabled)
                    except (ImportError, ValueError, requests.exceptions.RequestException) as e:
                        logger.exception(f"Error getting model names: {e}")
                        ids = GOOGLE_GENERATIVE_AI_MODELS
                build_config["model_name"]["options"] = ids
                build_config["model_name"]["value"] = ids[0]
            except Exception as e:
                msg = f"Error getting model names: {e}"
                raise ValueError(msg) from e
        return build_config
