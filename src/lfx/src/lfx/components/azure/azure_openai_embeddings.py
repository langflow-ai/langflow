from langchain_openai import AzureOpenAIEmbeddings

from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from lfx.field_typing import Embeddings
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput


class AzureOpenAIEmbeddingsComponent(LCModelComponent):
    display_name: str = "Azure OpenAI Embeddings"
    description: str = "Generate embeddings using Azure OpenAI models."
    documentation: str = "https://python.langchain.com/docs/integrations/text_embedding/azureopenai"
    icon = "Azure"
    name = "AzureOpenAIEmbeddings"

    API_VERSION_OPTIONS = [
        "2022-12-01",
        "2023-03-15-preview",
        "2023-05-15",
        "2023-06-01-preview",
        "2023-07-01-preview",
        "2023-08-01-preview",
    ]

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=OPENAI_EMBEDDING_MODEL_NAMES,
            value=OPENAI_EMBEDDING_MODEL_NAMES[0],
        ),
        MessageTextInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            required=True,
            info="Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
        ),
        MessageTextInput(
            name="azure_deployment",
            display_name="Deployment Name",
            required=True,
        ),
        DropdownInput(
            name="api_version",
            display_name="API Version",
            options=API_VERSION_OPTIONS,
            value=API_VERSION_OPTIONS[-1],
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Azure OpenAI API Key",
            required=True,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            embeddings = AzureOpenAIEmbeddings(
                model=self.model,
                azure_endpoint=self.azure_endpoint,
                azure_deployment=self.azure_deployment,
                api_version=self.api_version,
                api_key=self.api_key,
                dimensions=self.dimensions or None,
            )
        except Exception as e:
            msg = f"Could not connect to AzureOpenAIEmbeddings API: {e}"
            raise ValueError(msg) from e

        return embeddings
