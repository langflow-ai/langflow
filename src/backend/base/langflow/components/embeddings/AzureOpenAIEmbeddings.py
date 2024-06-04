from langchain_core.embeddings import Embeddings
from langchain_openai import AzureOpenAIEmbeddings
from pydantic.v1 import SecretStr

from langflow.custom import CustomComponent


class AzureOpenAIEmbeddingsComponent(CustomComponent):
    display_name: str = "Azure OpenAI Embeddings"
    description: str = "Generate embeddings using Azure OpenAI models."
    documentation: str = "https://python.langchain.com/docs/integrations/text_embedding/azureopenai"
    beta = False
    icon = "Azure"

    API_VERSION_OPTIONS = [
        "2022-12-01",
        "2023-03-15-preview",
        "2023-05-15",
        "2023-06-01-preview",
        "2023-07-01-preview",
        "2023-08-01-preview",
    ]

    def build_config(self):
        return {
            "azure_endpoint": {
                "display_name": "Azure Endpoint",
                "required": True,
                "info": "Your Azure endpoint, including the resource.. Example: `https://example-resource.azure.openai.com/`",
            },
            "azure_deployment": {
                "display_name": "Deployment Name",
                "required": True,
            },
            "api_version": {
                "display_name": "API Version",
                "options": self.API_VERSION_OPTIONS,
                "value": self.API_VERSION_OPTIONS[-1],
                "advanced": True,
            },
            "api_key": {
                "display_name": "API Key",
                "required": True,
                "password": True,
            },
            "code": {"show": False},
        }

    def build(
        self,
        azure_endpoint: str,
        azure_deployment: str,
        api_version: str,
        api_key: str,
    ) -> Embeddings:
        if api_key:
            azure_api_key = SecretStr(api_key)
        else:
            azure_api_key = None
        try:
            embeddings = AzureOpenAIEmbeddings(
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
                api_key=azure_api_key,
            )

        except Exception as e:
            raise ValueError("Could not connect to AzureOpenAIEmbeddings API.") from e

        return embeddings
