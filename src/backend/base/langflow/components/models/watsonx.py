import json
import logging
from typing import Any

import requests
from langchain_ibm import ChatWatsonx
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import BoolInput, DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput
from langflow.schema.dotdict import dotdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WatsonxAIComponent(LCModelComponent):
    display_name = "IBM watsonx.ai"
    description = "Generate text using IBM watsonx.ai foundation models"
    icon = "WatsonxAI"
    name = "IBMwatsonxModel"
    beta = False

    _default_models = ["ibm/granite-3-2b-instruct", "ibm/granite-3-8b-instruct", "ibm/granite-13b-instruct-v2"]

    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="url",
            display_name="watsonx API Endpoint",
            info="The base URL of the API.",
            value=None,
            options=[
                "https://us-south.ml.cloud.ibm.com",
                "https://eu-de.ml.cloud.ibm.com",
                "https://eu-gb.ml.cloud.ibm.com",
                "https://au-syd.ml.cloud.ibm.com",
                "https://jp-tok.ml.cloud.ibm.com",
                "https://ca-tor.ml.cloud.ibm.com",
            ],
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API Key to use for the model.",
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            value=None,
            dynamic=True,
            required=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate.",
            range_spec=RangeSpec(min=1, max=4096),
        ),
        StrInput(
            name="stop_sequence",
            display_name="Stop Sequence",
            advanced=True,
            info="Sequence where generation should stop.",
            field_type="str",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            advanced=True,
            info="Controls randomness, higher values increase diversity.",
            range_spec=RangeSpec(min=0, max=2),
            field_type="float",
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            advanced=True,
            info="The cumulative probability cutoff for token selection. "
            "Lower values mean sampling from a smaller, more top-weighted nucleus.",
            range_spec=RangeSpec(min=0, max=1),
            field_type="float",
        ),
        FloatInput(
            name="frequency_penalty",
            display_name="Frequency Penalty",
            advanced=True,
            info="Penalty for frequency of token usage.",
            range_spec=RangeSpec(min=-2.0, max=2.0),
        ),
        FloatInput(
            name="presence_penalty",
            display_name="Presence Penalty",
            advanced=True,
            info="Penalty for token presence in prior text.",
            range_spec=RangeSpec(min=-2.0, max=2.0),
        ),
        IntInput(
            name="seed",
            display_name="Random Seed",
            advanced=True,
            info="The random seed for the model.",
        ),
        BoolInput(
            name="logprobs",
            display_name="Log Probabilities",
            advanced=True,
            info="Whether to return log probabilities of the output tokens.",
        ),
        IntInput(
            name="top_logprobs",
            display_name="Top Log Probabilities",
            advanced=True,
            info="Number of most likely tokens to return at each position.",
            range_spec=RangeSpec(min=1, max=20),
        ),
        StrInput(
            name="logit_bias",
            display_name="Logit Bias",
            advanced=True,
            info='JSON string of token IDs to bias or suppress (e.g., {"1003": -100, "1004": 100}).',
            field_type="str",
        ),
    ]

    @staticmethod
    def fetch_models(base_url: str) -> list[str]:
        """Fetch available models from the watsonx.ai API."""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {"version": "2024-09-16", "filters": "function_text_chat,!lifecycle_withdrawn"}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["model_id"] for model in data.get("resources", [])]
            return sorted(models)
        except Exception:
            logger.exception("Error fetching models. Using default models.")
            return WatsonxAIComponent._default_models

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update model options when URL or API key changes."""
        logger.info("Updating build config. Field name: %s, Field value: %s", field_name, field_value)

        if field_name == "url" and field_value:
            try:
                models = self.fetch_models(base_url=build_config.url.value)
                build_config.model_name.options = models
                if build_config.model_name.value:
                    build_config.model_name.value = models[0]
                info_message = f"Updated model options: {len(models)} models found in {build_config.url.value}"
                logger.info(info_message)
            except Exception:
                logger.exception("Error updating model options.")

    def build_model(self) -> LanguageModel:
        # Parse logit_bias from JSON string if provided
        logit_bias = None
        if hasattr(self, "logit_bias") and self.logit_bias:
            try:
                logit_bias = json.loads(self.logit_bias)
            except json.JSONDecodeError:
                logger.warning("Invalid logit_bias JSON format. Using default instead.")
                logit_bias = {"1003": -100, "1004": -100}

        chat_params = {
            "max_tokens": getattr(self, "max_tokens", None) or 1000,
            "temperature": getattr(self, "temperature", None) or 0.7,
            "top_p": getattr(self, "top_p", None) or 0.9,
            "frequency_penalty": getattr(self, "frequency_penalty", None) or 0.5,
            "presence_penalty": getattr(self, "presence_penalty", None) or 0.3,
            "seed": getattr(self, "seed", None) or 8,
            "stop": [self.stop_sequence] if self.stop_sequence else [],
            "n": 1,
            "logprobs": getattr(self, "logprobs", True) or True,
            "top_logprobs": getattr(self, "top_logprobs", None) or 3,
            "time_limit": 600000,
            "logit_bias": logit_bias,
        }

        return ChatWatsonx(
            apikey=SecretStr(self.api_key).get_secret_value(),
            url=self.url,
            project_id=self.project_id,
            model_id=self.model_name,
            params=chat_params,
            streaming=self.stream,
        )
