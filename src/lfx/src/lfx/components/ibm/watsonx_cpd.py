import json
from typing import Any
import requests
from ibm_watsonx_ai import APIClient, Credentials
from langchain_ibm import ChatWatsonx
from loguru import logger
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, IntInput, SecretStrInput, SliderInput, StrInput, TabInput
from lfx.schema.dotdict import dotdict


class WatsonxAIComponentCPD(LCModelComponent):
    display_name = "IBM watsonx.ai / CPD"
    description = "Generate text using IBM watsonx.ai foundation models (SaaS or On-Prem / Cloud Pak for Data)."
    icon = "WatsonxAI"
    name = "IBMwatsonxModel"
    beta = False

    # These LLMs are used only for SaaS - On-Prem models as input field according to what has been deployed on-prem
    _default_models = [
        "ibm/granite-3-2b-instruct",
        "ibm/granite-3-8b-instruct",
        "ibm/granite-13b-instruct-v2",
    ]


    inputs = [
        TabInput(
            name="deployment_type",
            display_name="Deployment Type",
            info="Choose SaaS (IBM Cloud) or On-Prem (Cloud Pak for Data).",
            options=["On-Prem (CPD)", "SaaS"],
            value="On-Prem (CPD)",
            real_time_refresh=True,
        ),
        StrInput(
            name="url",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (e.g. https://eu-de.ml.cloud.ibm.com or your CPD URL).",
            required=True,
        ),
        StrInput(
            name="project_id",
            display_name="Project / Space ID",
            required=True,
            info="The project or deployment space ID associated with the model.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="IBM Cloud API key for SaaS use.",
            required=True,
            show=False,
        ),
        StrInput(
            name="username",
            display_name="Username",
            info="Cloud Pak for Data username.",
            required=True,
            show=True,
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            info="Cloud Pak for Data password.",
            required=True,
            show=True,
        ),
        StrInput(
            name="model_name",
            display_name="Model Name",
            dynamic=True,
            required=True,
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
            info="Cumulative probability cutoff for token sampling.",
            value=0.9,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        SliderInput(
            name="frequency_penalty",
            display_name="Frequency Penalty",
            info="Penalty for frequent token usage.",
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
            value=8,
        ),
        BoolInput(
            name="logprobs",
            display_name="Log Probabilities",
            advanced=True,
            value=True,
        ),
        IntInput(
            name="top_logprobs",
            display_name="Top Log Probabilities",
            advanced=True,
            value=3,
            range_spec=RangeSpec(min=1, max=20),
        ),
        StrInput(
            name="logit_bias",
            display_name="Logit Bias",
            advanced=True,
            info='JSON string of token IDs to bias/suppress, e.g. {"1003": -100, "1004": 100}.',
            field_type="str",
        ),
    ]

    @classmethod
    def fetch_models(cls, base_url: str) -> list[str]:
        """Fetch available SaaS models."""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {"version": "2024-09-16", "filters": "function_text_chat,!lifecycle_withdrawn"}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["model_id"] for model in data.get("resources", [])]
            return sorted(models)
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.exception("Error fetching SaaS models. Using defaults.")
            return cls._default_models

    def update_build_config(self, build_config: dotdict, _field_value: Any, field_name: str | None = None):
        """Update model dropdown based on environment."""
        deployment = build_config.deployment_type.value

        if deployment == "SaaS":
            build_config.api_key.show = True
            build_config.api_key.required = True
            build_config.username.show = False
            build_config.password.show = False
            build_config.username.required = False
            build_config.password.required = False
        else:
            build_config.api_key.show = False
            build_config.api_key.required = False
            build_config.username.show = True
            build_config.password.show = True
            build_config.username.required = True
            build_config.password.required = True

        if field_name in ("url", "deployment_type") and build_config.url.value:
            if deployment == "SaaS":
                try:
                    models = self.fetch_models(build_config.url.value)
                    build_config.model_name.options = models
                    build_config.model_name.value = models[0] if models else None
                    logger.info(f"Loaded {len(models)} SaaS models.")
                except (requests.RequestException, KeyError, ValueError) as e:
                    logger.exception("Error loading SaaS model list.")
            else:
                build_config.model_name.options = self._default_models
                build_config.model_name.value = self._default_models[0]
                logger.info("Using static CPD model list (on-prem).")

    def build_model(self) -> LanguageModel:
        """Construct ChatWatsonx client for SaaS or CPD."""
        # Parse logit bias
        logit_bias = None
        if getattr(self, "logit_bias", None):
            try:
                logit_bias = json.loads(self.logit_bias)
            except json.JSONDecodeError:
                logger.warning("Invalid logit_bias JSON; ignored.")

        chat_params = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "seed": self.seed,
            "stop": [self.stop_sequence] if self.stop_sequence else [],
            "n": 1,
            "logprobs": self.logprobs,
            "top_logprobs": self.top_logprobs,
            "time_limit": 600000,
            "logit_bias": logit_bias,
        }

        if self.deployment_type == "On-Prem (CPD)":
            # 🟢 CPD auth
            username = self.username or ""
            password = SecretStr(self.password).get_secret_value() if self.password else None
            try:
                credentials = Credentials(
                    url=self.url,
                    username=username,
                    password=password,
                    instance_id="openshift",
                    auth_type="cpd",
                )
            except TypeError:
                credentials = Credentials(
                    url=self.url,
                    username=username,
                    password=password,
                    instance_id="openshift",
                )

            api_client = APIClient(credentials)
            return ChatWatsonx(
                watsonx_client=api_client,
                model_id=self.model_name,
                project_id=self.project_id,
                params=chat_params,
                streaming=self.stream,
            )

        else:
            # 🟢 SaaS auth
            return ChatWatsonx(
                apikey=SecretStr(self.api_key).get_secret_value(),
                url=self.url,
                project_id=self.project_id,
                model_id=self.model_name,
                params=chat_params,
                streaming=self.stream,
            )
