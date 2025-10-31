from typing import Any

from langchain_openai import OpenAIEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.ollama_constants import OLLAMA_EMBEDDING_MODELS
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from lfx.base.models.watsonx_constants import WATSONX_EMBEDDING_MODEL_NAMES
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
from lfx.schema.dotdict import dotdict


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
        MessageTextInput(
            name="api_base",
            display_name="API Base URL",
            info="Base URL for the API. Leave empty for default.",
            advanced=True,
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

            return OllamaEmbeddings(
                model=model,
                base_url=api_base or "http://localhost:11434",
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
                "url": api_base or "https://us-south.ml.cloud.ibm.com",
                "apikey": api_key,
            }

            params["project_id"] = project_id

            return WatsonxEmbeddings(**params)

        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "provider":
            if field_value == "OpenAI":
                build_config["model"]["options"] = OPENAI_EMBEDDING_MODEL_NAMES
                build_config["model"]["value"] = OPENAI_EMBEDDING_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["required"] = True
                build_config["api_key"]["show"] = True
                build_config["api_base"]["display_name"] = "OpenAI API Base URL"
                build_config["api_base"]["advanced"] = True
                build_config["project_id"]["show"] = False

            elif field_value == "Ollama":
                build_config["model"]["options"] = OLLAMA_EMBEDDING_MODELS
                build_config["model"]["value"] = OLLAMA_EMBEDDING_MODELS[0]
                build_config["api_key"]["display_name"] = "API Key (Optional)"
                build_config["api_key"]["required"] = False
                build_config["api_key"]["show"] = False
                build_config["api_base"]["display_name"] = "Ollama Base URL"
                build_config["api_base"]["value"] = "http://localhost:11434"
                build_config["api_base"]["advanced"] = True
                build_config["project_id"]["show"] = False

            elif field_value == "IBM watsonx.ai":
                build_config["model"]["options"] = WATSONX_EMBEDDING_MODEL_NAMES
                build_config["model"]["value"] = WATSONX_EMBEDDING_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "IBM watsonx.ai API Key"
                build_config["api_key"]["required"] = True
                build_config["api_key"]["show"] = True
                build_config["api_base"]["display_name"] = "IBM watsonx.ai URL"
                build_config["api_base"]["value"] = "https://us-south.ml.cloud.ibm.com"
                build_config["api_base"]["advanced"] = False
                build_config["project_id"]["show"] = True

        return build_config
