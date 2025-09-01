import requests
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr
from typing_extensions import override

from langflow.base.models.cometapi_constants import MODEL_NAMES
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
)
from langflow.inputs.inputs import HandleInput
from langflow.logging import logger


class CometAPIModelComponent(LCModelComponent):
    display_name = "CometAPI"
    description = "Generates text using CometAPI LLMs (OpenAI compatible)."
    icon = "CometAPI"
    name = "CometAPIModel"

    # Constants
    API_BASE_URL = "https://api.cometapi.com/v1"
    REQUEST_TIMEOUT = 10

    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=MODEL_NAMES,
            value=MODEL_NAMES[0],
            refresh_button=True,
            combobox=True,
            info="Select a model from the dropdown or enter a custom model name.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="CometAPI API Key",
            info="The CometAPI API Key to use for CometAPI models.",
            advanced=False,
            value="COMETAPI_API_KEY",
            real_time_refresh=True,
        ),
        SliderInput(name="temperature", display_name="Temperature", value=0.1, range_spec=RangeSpec(min=0, max=1)),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for CometAPI calls."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_models(self) -> list[str]:
        """Fetch available models from CometAPI."""
        if not self.api_key:
            logger.warning("No API key provided, using default models")
            return MODEL_NAMES

        url = f"{self.API_BASE_URL}/models"
        headers = self._build_headers()

        try:
            logger.debug(f"Fetching models from CometAPI: {url}")
            response = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()

            model_list = response.json()
            models = [model["id"] for model in model_list.get("data", [])]

            if not models:
                logger.warning("No models returned from CometAPI, using default models")
            else:
                logger.debug(f"Successfully fetched {len(models)} models from CometAPI")
                return models

        except requests.exceptions.Timeout:
            error_msg = f"Timeout fetching models from CometAPI (>{self.REQUEST_TIMEOUT}s)"
            logger.error(error_msg)
            self.status = error_msg
            return MODEL_NAMES
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error fetching models: {e.response.status_code}"
            logger.error(error_msg)
            self.status = error_msg
            return MODEL_NAMES
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching models: {e}"
            logger.error(error_msg)
            self.status = error_msg
            return MODEL_NAMES
        except (KeyError, ValueError) as e:
            error_msg = f"Invalid response format from CometAPI: {e}"
            logger.error(error_msg)
            self.status = error_msg
            return MODEL_NAMES

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Update build configuration with fresh model list when API key changes."""
        if field_name in {"api_key", "model_name"}:
            models = self.get_models()
            build_config["model_name"]["options"] = models
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        """Build and configure the CometAPI language model."""
        if not self.api_key:
            msg = "CometAPI API Key is required"
            raise ValueError(msg)

        if not self.model_name:
            msg = "Model name is required"
            raise ValueError(msg)

        logger.debug(f"Building CometAPI model: {self.model_name}")

        try:
            output = ChatOpenAI(
                model=self.model_name,
                api_key=SecretStr(self.api_key).get_secret_value(),
                max_tokens=self.max_tokens or None,
                temperature=self.temperature,
                model_kwargs=self.model_kwargs or {},
                streaming=self.stream,
                seed=self.seed,
                base_url=self.API_BASE_URL,
            )
        except Exception as e:
            error_msg = f"Failed to initialize CometAPI model '{self.model_name}': {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        logger.debug(f"Successfully built CometAPI model: {self.model_name}")
        return output
