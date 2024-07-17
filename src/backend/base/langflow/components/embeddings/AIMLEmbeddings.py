from typing import Any
from langchain_openai.embeddings.base import OpenAIEmbeddings

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.components.embeddings.OllamaEmbeddings import OllamaEmbeddingsComponent
from langflow.components.embeddings.OpenAIEmbeddings import OpenAIEmbeddingsComponent
from langflow.custom.custom_component.component import Component
from langflow.field_typing import Embeddings
from langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput
from langflow.template.field.base import Output


class AIMLEmbeddingsComponent(Component):
    display_name = "AI/ML Embeddings"
    description = "Generate embeddings using the AI/ML API."
    icon = "OpenAI" # TODO: icon
    name = "AIMLEmbeddings"

    trace_type = "embedding"

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        build_config["json_mode"] = False
        return build_config
        if field_name == "model":
            if field_value == "text-embedding-3-small":
                return OpenAIEmbeddingsComponent.inputs

            if field_value == "meta-llama":
                return OllamaEmbeddingsComponent.inputs


        raise Exception(f"No model found for {field_value}")

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            options=[
                "meta-llama",
                "text-embedding-3-small",
                "text-embedding-3-large",
                "text-embedding-ada-002",
            ],
            value="text-embedding-3-small",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            value=True,
        )
    ]

    # inputs = [
    #     DictInput(
    #         name="default_headers",
    #         display_name="Default Headers",
    #         advanced=True,
    #         info="Default headers to use for the API request.",
    #     ),
    #     DictInput(
    #         name="default_query",
    #         display_name="Default Query",
    #         advanced=True,
    #         info="Default query parameters to use for the API request.",
    #     ),
    #     IntInput(name="chunk_size", display_name="Chunk Size", advanced=True, value=1000),
    #     MessageTextInput(name="client", display_name="Client", advanced=True),
    #     MessageTextInput(name="deployment", display_name="Deployment", advanced=True),
    #     IntInput(name="embedding_ctx_length", display_name="Embedding Context Length", advanced=True, value=1536),
    #     IntInput(name="max_retries", display_name="Max Retries", value=3, advanced=True),
    #     DropdownInput(
    #         name="model",
    #         display_name="Model",
    #         advanced=False,
    #         options=[
    #             # TODO: Add the rest to a constant
    #             "meta-llama",
    #             "text-embedding-3-small",
    #             "text-embedding-3-large",
    #             "text-embedding-ada-002",
    #         ],
    #         value="text-embedding-3-small",
    #     ),
    #     DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
    #     SecretStrInput(name="openai_api_key", display_name="OpenAI API Key", value="OPENAI_API_KEY"),
    #     FloatInput(name="request_timeout", display_name="Request Timeout", advanced=True),
    #     BoolInput(name="skip_empty", display_name="Skip Empty", advanced=True),
    #     MessageTextInput(
    #         name="tiktoken_model_name",
    #         display_name="TikToken Model Name",
    #         advanced=True,
    #     ),
    #     BoolInput(
    #         name="tiktoken_enable",
    #         display_name="TikToken Enable",
    #         advanced=True,
    #         value=True,
    #         info="If False, you must have transformers installed.",
    #     ),
    #     IntInput(
    #         name="dimensions",
    #         display_name="Dimensions",
    #         info="The number of dimensions the resulting output embeddings should have. Only supported by certain models.",
    #         advanced=True,
    #     ),
    # ]

    def build_embeddings(self) -> Embeddings:
        return OpenAIEmbeddings(
            tiktoken_enabled=self.tiktoken_enable,
            default_headers=self.default_headers,
            default_query=self.default_query,
            allowed_special="all",
            disallowed_special="all",
            chunk_size=self.chunk_size,
            deployment=self.deployment,
            embedding_ctx_length=self.embedding_ctx_length,
            max_retries=self.max_retries,
            model=self.model,
            model_kwargs=self.model_kwargs,
            base_url=self.openai_api_base,
            api_key=self.openai_api_key,
            openai_api_type=self.openai_api_type,
            api_version=self.openai_api_version,
            organization=self.openai_organization,
            openai_proxy=self.openai_proxy,
            timeout=self.request_timeout or None,
            show_progress_bar=self.show_progress_bar,
            skip_empty=self.skip_empty,
            tiktoken_model_name=self.tiktoken_model_name,
            dimensions=self.dimensions or None,
        )
