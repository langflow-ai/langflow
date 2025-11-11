from typing import Any

from langchain_openai import OpenAIEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.model_utils import get_ollama_models, is_valid_ollama_url
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS, WATSONX_EMBEDDING_MODEL_NAMES
from lfx.field_typing import Embeddings
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict
from lfx.utils.util import transform_localhost_url

# Ollama API constants
HTTP_STATUS_OK = 200
JSON_MODELS_KEY = "models"
JSON_NAME_KEY = "name"
JSON_CAPABILITIES_KEY = "capabilities"
DESIRED_CAPABILITY = "embedding"
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class EmbeddingModelComponent(LCEmbeddingsModel):
    display_name = "Embedding Model"
    description = "Generate embeddings using a specified provider."
    documentation: str = "https://docs.langflow.org/components-embedding-models"
    icon = "binary"
    name = "EmbeddingModel"
    category = "models"

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            options=["OpenAI", "Ollama", "IBM watsonx.ai"],
            value="OpenAI",
            info="Select the embedding model provider",
            real_time_refresh=True,
            options_metadata=[{"icon": "OpenAI"}, {"icon": "Ollama"}, {"icon": "WatsonxAI"}],
        ),
        MessageTextInput(
            name="api_base",
            display_name="API Base URL",
            info="Base URL for the API. Leave empty for default.",
            advanced=True,
        ),
        MessageTextInput(
            name="ollama_base_url",
            display_name="Ollama API URL",
            info=f"Endpoint of the Ollama API (Ollama only). Defaults to {DEFAULT_OLLAMA_URL}",
            value=DEFAULT_OLLAMA_URL,
            show=False,
            real_time_refresh=True,
            load_from_db=True,
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
        DropdownInput(
            name="model",
            display_name="Model Name",
            options=OPENAI_EMBEDDING_MODEL_NAMES,
            value=OPENAI_EMBEDDING_MODEL_NAMES[0],
            info="Select the embedding model to use",
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="Model Provider API key",
            required=True,
            show=True,
            real_time_refresh=True,
        ),
        # Watson-specific inputs
        MessageTextInput(
            name="project_id",
            display_name="Project ID",
            info="IBM watsonx.ai Project ID (required for IBM watsonx.ai)",
            show=False,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models.",
            advanced=True,
        ),
        IntInput(name="chunk_size", display_name="Chunk Size", advanced=True, value=1000),
        FloatInput(name="request_timeout", display_name="Request Timeout", advanced=True),
        IntInput(name="max_retries", display_name="Max Retries", advanced=True, value=3),
        BoolInput(name="show_progress_bar", display_name="Show Progress Bar", advanced=True),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        provider = self.provider
        model = self.model
        api_key = self.api_key
        api_base = self.api_base
        base_url_ibm_watsonx = self.base_url_ibm_watsonx
        ollama_base_url = self.ollama_base_url
        dimensions = self.dimensions
        chunk_size = self.chunk_size
        request_timeout = self.request_timeout
        max_retries = self.max_retries
        show_progress_bar = self.show_progress_bar
        model_kwargs = self.model_kwargs or {}

        if provider == "OpenAI":
            if not api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)
            return OpenAIEmbeddings(
                model=model,
                dimensions=dimensions or None,
                base_url=api_base or None,
                api_key=api_key,
                chunk_size=chunk_size,
                max_retries=max_retries,
                timeout=request_timeout or None,
                show_progress_bar=show_progress_bar,
                model_kwargs=model_kwargs,
            )

        if provider == "Ollama":
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError:
                try:
                    from langchain_community.embeddings import OllamaEmbeddings
                except ImportError:
                    msg = "Please install langchain-ollama: pip install langchain-ollama"
                    raise ImportError(msg) from None

            transformed_base_url = transform_localhost_url(ollama_base_url)

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

            return OllamaEmbeddings(
                model=model,
                base_url=transformed_base_url or "http://localhost:11434",
                **model_kwargs,
            )

        if provider == "IBM watsonx.ai":
            try:
                from langchain_ibm import WatsonxEmbeddings
            except ImportError:
                msg = "Please install langchain-ibm: pip install langchain-ibm"
                raise ImportError(msg) from None

            if not api_key:
                msg = "IBM watsonx.ai API key is required when using IBM watsonx.ai provider"
                raise ValueError(msg)

            project_id = self.project_id

            if not project_id:
                msg = "Project ID is required for IBM watsonx.ai provider"
                raise ValueError(msg)

            params = {
                "model_id": model,
                "url": base_url_ibm_watsonx or "https://us-south.ml.cloud.ibm.com",
                "apikey": api_key,
            }

            params["project_id"] = project_id

            return WatsonxEmbeddings(**params)

        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    async def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict:
        if field_name == "provider":
            if field_value == "OpenAI":
                build_config["model"]["options"] = OPENAI_EMBEDDING_MODEL_NAMES
                build_config["model"]["value"] = OPENAI_EMBEDDING_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["required"] = True
                build_config["api_key"]["show"] = True
                build_config["api_base"]["display_name"] = "OpenAI API Base URL"
                build_config["api_base"]["advanced"] = True
                build_config["api_base"]["show"] = True
                build_config["ollama_base_url"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["base_url_ibm_watsonx"]["show"] = False

            elif field_value == "Ollama":
                build_config["ollama_base_url"]["show"] = True

                if await is_valid_ollama_url(url=self.ollama_base_url):
                    try:
                        models = await get_ollama_models(
                            base_url_value=self.ollama_base_url,
                            desired_capability=DESIRED_CAPABILITY,
                            json_models_key=JSON_MODELS_KEY,
                            json_name_key=JSON_NAME_KEY,
                            json_capabilities_key=JSON_CAPABILITIES_KEY,
                        )
                        build_config["model"]["options"] = models
                        build_config["model"]["value"] = models[0] if models else ""
                    except ValueError:
                        build_config["model"]["options"] = []
                        build_config["model"]["value"] = ""
                else:
                    build_config["model"]["options"] = []
                    build_config["model"]["value"] = ""

                build_config["api_key"]["display_name"] = "API Key (Optional)"
                build_config["api_key"]["required"] = False
                build_config["api_key"]["show"] = False
                build_config["api_base"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["base_url_ibm_watsonx"]["show"] = False

            elif field_value == "IBM watsonx.ai":
                build_config["model"]["options"] = WATSONX_EMBEDDING_MODEL_NAMES
                build_config["model"]["value"] = WATSONX_EMBEDDING_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "IBM watsonx.ai API Key"
                build_config["api_key"]["required"] = True
                build_config["api_key"]["show"] = True
                build_config["api_base"]["show"] = False
                build_config["ollama_base_url"]["show"] = False
                build_config["base_url_ibm_watsonx"]["show"] = True
                build_config["project_id"]["show"] = True

        elif field_name == "ollama_base_url":
            # # Refresh Ollama models when base URL changes
            # if hasattr(self, "provider") and self.provider == "Ollama":
            # Use field_value if provided, otherwise fall back to instance attribute
            ollama_url = self.ollama_base_url
            if await is_valid_ollama_url(url=ollama_url):
                try:
                    models = await get_ollama_models(
                        base_url_value=ollama_url,
                        desired_capability=DESIRED_CAPABILITY,
                        json_models_key=JSON_MODELS_KEY,
                        json_name_key=JSON_NAME_KEY,
                        json_capabilities_key=JSON_CAPABILITIES_KEY,
                    )
                    build_config["model"]["options"] = models
                    build_config["model"]["value"] = models[0] if models else ""
                except ValueError:
                    await logger.awarning("Failed to fetch Ollama embedding models.")
                    build_config["model"]["options"] = []
                    build_config["model"]["value"] = ""

        elif field_name == "model" and self.provider == "Ollama":
            ollama_url = self.ollama_base_url
            if await is_valid_ollama_url(url=ollama_url):
                try:
                    models = await get_ollama_models(
                        base_url_value=ollama_url,
                        desired_capability=DESIRED_CAPABILITY,
                        json_models_key=JSON_MODELS_KEY,
                        json_name_key=JSON_NAME_KEY,
                        json_capabilities_key=JSON_CAPABILITIES_KEY,
                    )
                    build_config["model"]["options"] = models
                except ValueError:
                    await logger.awarning("Failed to refresh Ollama embedding models.")
                    build_config["model"]["options"] = []

        return build_config
