from typing import Any

import requests
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames
from langchain_ibm import WatsonxEmbeddings
from loguru import logger
from pydantic.v1 import SecretStr

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.field_typing import Embeddings
from lfx.io import BoolInput, DropdownInput, IntInput, SecretStrInput, StrInput
from lfx.schema.dotdict import dotdict


class WatsonxEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "IBM watsonx.ai Embeddings"
    description = "Generate embeddings using IBM watsonx.ai models."
    icon = "WatsonxAI"
    name = "WatsonxEmbeddingsComponent"

    # models present in all the regions
    _default_models = [
        "sentence-transformers/all-minilm-l12-v2",
        "ibm/slate-125m-english-rtrvr-v2",
        "ibm/slate-30m-english-rtrvr-v2",
        "intfloat/multilingual-e5-large",
    ]

    inputs = [
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
            display_name="watsonx project id",
            info="The project ID or deployment space ID that is associated with the foundation model.",
            required=True,
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
            name="truncate_input_tokens",
            display_name="Truncate Input Tokens",
            advanced=True,
            value=200,
        ),
        BoolInput(
            name="input_text",
            display_name="Include the original text in the output",
            value=True,
            advanced=True,
        ),
    ]

    @staticmethod
    def fetch_models(base_url: str) -> list[str]:
        """Fetch available models from the watsonx.ai API."""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {
                "version": "2024-09-16",
                "filters": "function_embedding,!lifecycle_withdrawn:and",
            }
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [model["model_id"] for model in data.get("resources", [])]
            return sorted(models)
        except Exception:  # noqa: BLE001
            logger.exception("Error fetching models")
            return WatsonxEmbeddingsComponent._default_models

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update model options when URL or API key changes."""
        logger.debug(
            "Updating build config. Field name: %s, Field value: %s",
            field_name,
            field_value,
        )

        if field_name == "url" and field_value:
            try:
                models = self.fetch_models(base_url=build_config.url.value)
                build_config.model_name.options = models
                if build_config.model_name.value:
                    build_config.model_name.value = models[0]
                info_message = f"Updated model options: {len(models)} models found in {build_config.url.value}"
                logger.info(info_message)
            except Exception:  # noqa: BLE001
                logger.exception("Error updating model options.")

    def build_embeddings(self) -> Embeddings:
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
