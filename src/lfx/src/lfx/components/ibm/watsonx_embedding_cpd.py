from typing import Any
import requests
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames
from langchain_ibm import WatsonxEmbeddings
from loguru import logger
from pydantic.v1 import SecretStr

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.field_typing import Embeddings
from lfx.io import BoolInput, IntInput, SecretStrInput, StrInput, TabInput
from lfx.schema.dotdict import dotdict


class WatsonxEmbeddingsComponentCPD(LCEmbeddingsModel):
    display_name = "IBM watsonx.ai / CPD Embeddings"
    description = "Generate embeddings using IBM watsonx.ai SaaS or On-Prem (Cloud Pak for Data)."
    icon = "WatsonxAI"
    name = "WatsonxEmbeddingsComponent"

 # These LLMs are used only for SaaS - On-Prem models as input field according to what has been deployed on-prem
    _default_models = [
        "ibm/slate-30m-english-rtrvr-v2",
        "ibm/slate-125m-english-rtrvr-v2",
        "sentence-transformers/all-minilm-l12-v2",
        "intfloat/multilingual-e5-large",
    ]

    inputs = [
        TabInput(
            name="deployment_type",
            display_name="Deployment Type",
            info="Choose SaaS or On-Prem (CPD) connection type.",
            options=["On-Prem (CPD)", "SaaS"],
            value="On-Prem (CPD)",
            real_time_refresh=True,
        ),
        StrInput(
            name="url",
            display_name="watsonx API Endpoint",
            info="Base URL (e.g. https://eu-de.ml.cloud.ibm.com or your CPD cluster URL).",
            required=True,
        ),
        StrInput(
            name="project_id",
            display_name="Project ID",
            info="Project or space ID associated with the model.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="IBM Cloud API key for SaaS.",
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
            required=True,
        ),
        IntInput(
            name="truncate_input_tokens",
            display_name="Truncate Input Tokens",
            advanced=True,
            value=200,
        ),
        BoolInput(
            name="input_text",
            display_name="Include original text in output",
            value=True,
            advanced=True,
        ),
    ]

    @classmethod
    def fetch_models(cls, base_url: str) -> list[str]:
        """Fetch available models (SaaS only)."""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {"version": "2024-09-16", "filters": "function_embedding,!lifecycle_withdrawn:and"}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["model_id"] for model in data.get("resources", [])]
            return sorted(models)
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.exception("Could not fetch models from SaaS API.")
            return cls._default_models

    def update_build_config(self, build_config: dotdict, _field_value: Any, field_name: str | None = None):
        """Update model dropdown when connection type changes."""
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
                    logger.info(f"Loaded {len(models)} models from SaaS.")
                except (requests.RequestException, KeyError, ValueError) as e:
                    logger.exception("Error loading SaaS models.")
            else:
                # On-Prem fallback – static model list
                build_config.model_name.options = self._default_models
                build_config.model_name.value = self._default_models[0]
                logger.info("Using static CPD model list (on-prem).")

    def build_embeddings(self) -> Embeddings:
        """Create watsonx.ai embeddings client."""
        if self.deployment_type == "On-Prem (CPD)":
            password = SecretStr(self.password).get_secret_value() if self.password else None
            username = self.username or ""

            # 🔹 Cloud Pak for Data (on-prem) credentials
            try:
                credentials = Credentials(
                    url=self.url,
                    username=username,
                    password=password,
                    instance_id="openshift",  
                    auth_type="cpd",
                )
            except TypeError:
                # fallback jos auth_type ei kelpaa kirjastoversiossa
                credentials = Credentials(
                    url=self.url,
                    username=username,
                    password=password,
                    instance_id="openshift",
                )

        else:
            # SaaS credentials
            credentials = Credentials(
                api_key=SecretStr(self.api_key).get_secret_value(),
                url=self.url,
            )

        api_client = APIClient(credentials)

        params = {
            EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS: self.truncate_input_tokens,
            EmbedTextParamsMetaNames.RETURN_OPTIONS: {"input_text": self.input_text},
        }

        return WatsonxEmbeddings(
            model_id=self.model_name,
            params=params,
            watsonx_client=api_client,
            project_id=self.project_id,
        )
