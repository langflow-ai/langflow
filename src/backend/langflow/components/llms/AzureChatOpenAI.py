from typing import Optional
from langflow import CustomComponent
from langchain.llms.base import BaseLanguageModel
from langchain.chat_models.azure_openai import AzureChatOpenAI


class AzureChatOpenAIComponent(CustomComponent):
    display_name: str = "AzureChatOpenAI"
    description: str = "LLM model from Azure OpenAI."
    documentation: str = "https://python.langchain.com/docs/integrations/llms/azure_openai"

    AZURE_OPENAI_MODELS = [
        "gpt-35-turbo",
        "gpt-35-turbo-16k",
        "gpt-35-turbo-instruct",
        "gpt-4",
        "gpt-4-32k",
        "gpt-4-vision",
    ]

    def build_config(self):
        return {
            "model": {
                "display_name": "Model Name",
                "value": "gpt-35-turbo",
                "options": self.AZURE_OPENAI_MODELS,
                "required": True,
            },
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
                "value": "2023-05-15",
                "required": True,
                "advanced": True,
            },
            "api_key": {"display_name": "API Key", "required": True, "password": True},
            "temperature": {
                "display_name": "Temperature",
                "value": 0.7,
                "field_type": "float",
                "required": False,
            },
            "max_tokens": {
                "display_name": "Max Tokens",
                "value": 1000,
                "required": False,
                "field_type": "int",
                "advanced": True,
            },
            "code": {"show": False},
        }

    def build(
        self,
        model: str,
        azure_endpoint: str,
        azure_deployment: str,
        api_key: str,
        api_version: str = "2023-05-15",
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000,
    ) -> BaseLanguageModel:
        return AzureChatOpenAI(
            model=model,
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment,
            api_version=api_version,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
