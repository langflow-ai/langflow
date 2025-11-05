from typing import Any
from urllib.parse import urljoin

import requests
from langchain_anthropic import ChatAnthropic
from langchain_ibm import ChatWatsonx
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed
from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES, OPENAI_REASONING_MODEL_NAMES
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, MessageTextInput, StrInput
from lfx.io import DropdownInput, MessageInput, MultilineInput, SecretStrInput, SliderInput
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict
from lfx.utils.util import transform_localhost_url

# IBM watsonx.ai constants
IBM_WATSONX_DEFAULT_MODELS = ["ibm/granite-3-2b-instruct", "ibm/granite-3-8b-instruct", "ibm/granite-13b-instruct-v2"]
IBM_WATSONX_URLS = [
    "https://us-south.ml.cloud.ibm.com",
    "https://eu-de.ml.cloud.ibm.com",
    "https://eu-gb.ml.cloud.ibm.com",
    "https://au-syd.ml.cloud.ibm.com",
    "https://jp-tok.ml.cloud.ibm.com",
    "https://ca-tor.ml.cloud.ibm.com",
]


class LanguageModelComponent(LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 0  # Set priority to 0 to make it appear first

    @staticmethod
    def fetch_ibm_models(base_url: str) -> list[str]:
        """Fetch available models from the watsonx.ai API."""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {"version": "2024-09-16", "filters": "function_text_chat,!lifecycle_withdrawn"}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["model_id"] for model in data.get("resources", [])]
            return sorted(models)
        except Exception:  # noqa: BLE001
            logger.exception("Error fetching IBM watsonx models. Using default models.")
            return IBM_WATSONX_DEFAULT_MODELS

    @staticmethod
    def fetch_ollama_models(base_url: str) -> list[str]:
        """Fetch available models from the Ollama API."""
        try:
            # Strip /v1 suffix if present, as Ollama API endpoints are at root level
            base_url = base_url.rstrip("/").removesuffix("/v1")
            if not base_url.endswith("/"):
                base_url = base_url + "/"
            base_url = transform_localhost_url(base_url)

            # Ollama REST API to return models
            tags_url = urljoin(base_url, "api/tags")

            response = requests.get(tags_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return sorted(models)
        except Exception:  # noqa: BLE001
            logger.exception("Error fetching Ollama models. Returning empty list.")
            return []

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            options=["OpenAI", "Anthropic", "Google", "IBM watsonx.ai", "Ollama"],
            value="OpenAI",
            info="Select the model provider",
            real_time_refresh=True,
            options_metadata=[
                {"icon": "OpenAI"},
                {"icon": "Anthropic"},
                {"icon": "GoogleGenerativeAI"},
                {"icon": "WatsonxAI"},
                {"icon": "Ollama"},
            ],
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES,
            value=OPENAI_CHAT_MODEL_NAMES[0],
            info="Select the model to use",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="Model Provider API key",
            required=False,
            show=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
            info="The project ID associated with the foundation model (IBM watsonx.ai only)",
            show=False,
            required=False,
        ),
        MessageTextInput(
            name="ollama_base_url",
            display_name="Ollama API URL",
            info="Endpoint of the Ollama API (Ollama only). Defaults to http://localhost:11434",
            value="http://localhost:11434",
            show=False,
            real_time_refresh=True,
        ),
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The input text to send to the model",
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="A system message that helps set the behavior of the assistant",
            advanced=False,
        ),
        BoolInput(
            name="stream",
            display_name="Stream",
            info="Whether to stream the response",
            value=False,
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Controls randomness in responses",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:
        provider = self.provider
        model_name = self.model_name
        temperature = self.temperature
        stream = self.stream

        if provider == "OpenAI":
            if not self.api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)

            if model_name in OPENAI_REASONING_MODEL_NAMES:
                # reasoning models do not support temperature (yet)
                temperature = None

            return ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                streaming=stream,
                openai_api_key=self.api_key,
            )
        if provider == "Anthropic":
            if not self.api_key:
                msg = "Anthropic API key is required when using Anthropic provider"
                raise ValueError(msg)
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                anthropic_api_key=self.api_key,
            )
        if provider == "Google":
            if not self.api_key:
                msg = "Google API key is required when using Google provider"
                raise ValueError(msg)
            return ChatGoogleGenerativeAIFixed(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                google_api_key=self.api_key,
            )
        if provider == "IBM watsonx.ai":
            if not self.api_key:
                msg = "IBM API key is required when using IBM watsonx.ai provider"
                raise ValueError(msg)
            if not self.base_url_ibm_watsonx:
                msg = "IBM watsonx API Endpoint is required when using IBM watsonx.ai provider"
                raise ValueError(msg)
            if not self.project_id:
                msg = "IBM watsonx Project ID is required when using IBM watsonx.ai provider"
                raise ValueError(msg)
            return ChatWatsonx(
                apikey=SecretStr(self.api_key).get_secret_value(),
                url=self.base_url_ibm_watsonx,
                project_id=self.project_id,
                model_id=model_name,
                params={
                    "temperature": temperature,
                },
                streaming=stream,
            )
        if provider == "Ollama":
            if not self.ollama_base_url:
                msg = "Ollama API URL is required when using Ollama provider"
                raise ValueError(msg)
            if not model_name:
                msg = "Model name is required when using Ollama provider"
                raise ValueError(msg)

            transformed_base_url = transform_localhost_url(self.ollama_base_url)

            # Check if URL contains /v1 suffix (OpenAI-compatible mode)
            if transformed_base_url and transformed_base_url.rstrip("/").endswith("/v1"):
                # Strip /v1 suffix and log warning
                transformed_base_url = transformed_base_url.rstrip("/").removesuffix("/v1")
                logger.warning(
                    "Detected '/v1' suffix in base URL. The Ollama component uses the native Ollama API, "
                    "not the OpenAI-compatible API. The '/v1' suffix has been automatically removed. "
                    "If you want to use the OpenAI-compatible API, please use the OpenAI component instead. "
                    "Learn more at https://docs.ollama.com/openai#openai-compatibility"
                )

            return ChatOllama(
                base_url=transformed_base_url,
                model=model_name,
                temperature=temperature,
            )
        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "provider":
            if field_value == "OpenAI":
                build_config["model_name"]["options"] = OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES
                build_config["model_name"]["value"] = OPENAI_CHAT_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["show"] = True
                build_config["base_url_ibm_watsonx"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["ollama_base_url"]["show"] = False
            elif field_value == "Anthropic":
                build_config["model_name"]["options"] = ANTHROPIC_MODELS
                build_config["model_name"]["value"] = ANTHROPIC_MODELS[0]
                build_config["api_key"]["display_name"] = "Anthropic API Key"
                build_config["api_key"]["show"] = True
                build_config["base_url_ibm_watsonx"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["ollama_base_url"]["show"] = False
            elif field_value == "Google":
                build_config["model_name"]["options"] = GOOGLE_GENERATIVE_AI_MODELS
                build_config["model_name"]["value"] = GOOGLE_GENERATIVE_AI_MODELS[0]
                build_config["api_key"]["display_name"] = "Google API Key"
                build_config["api_key"]["show"] = True
                build_config["base_url_ibm_watsonx"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["ollama_base_url"]["show"] = False
            elif field_value == "IBM watsonx.ai":
                build_config["model_name"]["options"] = IBM_WATSONX_DEFAULT_MODELS
                build_config["model_name"]["value"] = IBM_WATSONX_DEFAULT_MODELS[0]
                build_config["api_key"]["display_name"] = "IBM API Key"
                build_config["api_key"]["show"] = True
                build_config["base_url_ibm_watsonx"]["show"] = True
                build_config["project_id"]["show"] = True
                build_config["ollama_base_url"]["show"] = False
            elif field_value == "Ollama":
                # Fetch Ollama models from the API
                ollama_url = build_config["ollama_base_url"].get("value", "http://localhost:11434")
                models = self.fetch_ollama_models(base_url=ollama_url)
                build_config["model_name"]["options"] = models
                build_config["model_name"]["value"] = models[0] if models else ""
                build_config["api_key"]["show"] = False
                build_config["base_url_ibm_watsonx"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["ollama_base_url"]["show"] = True
        elif (
            field_name == "base_url_ibm_watsonx"
            and field_value
            and hasattr(self, "provider")
            and self.provider == "IBM watsonx.ai"
        ):
            # Fetch IBM models when base_url changes
            try:
                models = self.fetch_ibm_models(base_url=field_value)
                build_config["model_name"]["options"] = models
                build_config["model_name"]["value"] = models[0] if models else IBM_WATSONX_DEFAULT_MODELS[0]
                info_message = f"Updated model options: {len(models)} models found in {field_value}"
                logger.info(info_message)
            except Exception:  # noqa: BLE001
                logger.exception("Error updating IBM model options.")
        elif (
            field_name == "ollama_base_url" and field_value and hasattr(self, "provider") and self.provider == "Ollama"
        ):
            # Fetch Ollama models when ollama_base_url changes
            try:
                models = self.fetch_ollama_models(base_url=field_value)
                build_config["model_name"]["options"] = models
                build_config["model_name"]["value"] = models[0] if models else ""
                info_message = f"Updated model options: {len(models)} models found in {field_value}"
                logger.info(info_message)
            except Exception:  # noqa: BLE001
                logger.exception("Error updating Ollama model options.")
        elif field_name == "model_name" and field_value.startswith("o1") and self.provider == "OpenAI":
            # Hide system_message for o1 models - currently unsupported
            if "system_message" in build_config:
                build_config["system_message"]["show"] = False
        elif field_name == "model_name" and not field_value.startswith("o1") and "system_message" in build_config:
            build_config["system_message"]["show"] = True
        return build_config
