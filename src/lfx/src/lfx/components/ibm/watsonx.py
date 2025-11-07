import json
from typing import Any

import requests
from langchain_ibm import ChatWatsonx
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict


class WatsonxAIComponent(LCModelComponent):
    display_name = "IBM watsonx.ai"
    description = "Generate text using IBM watsonx.ai foundation models."
    icon = "WatsonxAI"
    name = "IBMwatsonxModel"
    beta = False

    _default_models = ["ibm/granite-3-2b-instruct", "ibm/granite-3-8b-instruct", "ibm/granite-13b-instruct-v2"]
    _urls = [
        "https://us-south.ml.cloud.ibm.com",
        "https://eu-de.ml.cloud.ibm.com",
        "https://eu-gb.ml.cloud.ibm.com",
        "https://au-syd.ml.cloud.ibm.com",
        "https://jp-tok.ml.cloud.ibm.com",
        "https://ca-tor.ml.cloud.ibm.com",
    ]
    inputs = [
        *LCModelComponent.get_base_inputs(),
        DropdownInput(
            name="base_url",
            display_name="watsonx API Endpoint",
            info="The base URL of the API.",
            value=[],
            options=_urls,
            real_time_refresh=True,
            required=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
            required=True,
            info="The project ID or deployment space ID that is associated with the foundation model.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Watsonx API Key",
            info="The API Key to use for the model.",
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            value=None,
            real_time_refresh=True,
            required=True,
            refresh_button=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate.",
            range_spec=RangeSpec(min=1, max=4096),
            value=1000,
        ),
        StrInput(
            name="stop_sequence",
            display_name="Stop Sequence",
            advanced=True,
            info="Sequence where generation should stop.",
            field_type="str",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness, higher values increase diversity.",
            value=0.1,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        SliderInput(
            name="top_p",
            display_name="Top P",
            info="The cumulative probability cutoff for token selection. "
            "Lower values mean sampling from a smaller, more top-weighted nucleus.",
            value=0.9,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        SliderInput(
            name="frequency_penalty",
            display_name="Frequency Penalty",
            info="Penalty for frequency of token usage.",
            value=0.5,
            range_spec=RangeSpec(min=-2.0, max=2.0, step=0.01),
            advanced=True,
        ),
        SliderInput(
            name="presence_penalty",
            display_name="Presence Penalty",
            info="Penalty for token presence in prior text.",
            value=0.3,
            range_spec=RangeSpec(min=-2.0, max=2.0, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Random Seed",
            advanced=True,
            info="The random seed for the model.",
            value=8,
        ),
        BoolInput(
            name="logprobs",
            display_name="Log Probabilities",
            advanced=True,
            info="Whether to return log probabilities of the output tokens.",
            value=True,
        ),
        IntInput(
            name="top_logprobs",
            display_name="Top Log Probabilities",
            advanced=True,
            info="Number of most likely tokens to return at each position.",
            value=3,
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
        except Exception:  # noqa: BLE001
            logger.exception("Error fetching models. Using default models.")
            return WatsonxAIComponent._default_models

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update model options when URL or API key changes."""
        if field_name == "base_url" and field_value:
            try:
                models = self.fetch_models(base_url=field_value)
                build_config["model_name"]["options"] = models
                if build_config["model_name"]["value"]:
                    build_config["model_name"]["value"] = models[0]
                info_message = f"Updated model options: {len(models)} models found in {field_value}"
                logger.info(info_message)
            except Exception:  # noqa: BLE001
                logger.exception("Error updating model options.")
        if field_name == "model_name" and field_value and field_value in WatsonxAIComponent._urls:
            build_config["model_name"]["options"] = self.fetch_models(base_url=field_value)
            build_config["model_name"]["value"] = ""
        return build_config

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
            "max_tokens": getattr(self, "max_tokens", None),
            "temperature": getattr(self, "temperature", None),
            "top_p": getattr(self, "top_p", None),
            "frequency_penalty": getattr(self, "frequency_penalty", None),
            "presence_penalty": getattr(self, "presence_penalty", None),
            "seed": getattr(self, "seed", None),
            "stop": [self.stop_sequence] if self.stop_sequence else [],
            "n": 1,
            "logprobs": getattr(self, "logprobs", True),
            "top_logprobs": getattr(self, "top_logprobs", None),
            "time_limit": 600000,
            "logit_bias": logit_bias,
        }

        return ChatWatsonx(
            apikey=SecretStr(self.api_key).get_secret_value(),
            url=self.base_url,
            project_id=self.project_id,
            model_id=self.model_name,
            params=chat_params,
            streaming=self.stream,
        )
