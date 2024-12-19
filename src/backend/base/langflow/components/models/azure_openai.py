from langchain_openai import AzureChatOpenAI

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import MessageTextInput
from langflow.io import DropdownInput, FloatInput, IntInput, SecretStrInput


class AzureChatOpenAIComponent(LCModelComponent):
    display_name: str = "Azure OpenAI"
    description: str = "Generate text using Azure OpenAI LLMs."
    documentation: str = "https://python.langchain.com/docs/integrations/llms/azure_openai"
    beta = False
    icon = "Azure"
    name = "AzureOpenAIModel"

    AZURE_OPENAI_API_VERSIONS = [
        "2024-06-01",
        "2024-07-01-preview",
        "2024-08-01-preview",
        "2024-09-01-preview",
        "2024-10-01-preview",
        "2023-05-15",
        "2023-12-01-preview",
        "2024-02-15-preview",
        "2024-03-01-preview",
    ]

    inputs = [
        *LCModelComponent._base_inputs,
        MessageTextInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            info="Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
            required=True,
        ),
        MessageTextInput(name="azure_deployment", display_name="Deployment Name", required=True),
        SecretStrInput(name="api_key", display_name="API Key"),
        DropdownInput(
            name="api_version",
            display_name="API Version",
            options=sorted(AZURE_OPENAI_API_VERSIONS, reverse=True),
            value=next(
                (
                    version
                    for version in sorted(AZURE_OPENAI_API_VERSIONS, reverse=True)
                    if not version.endswith("-preview")
                ),
                AZURE_OPENAI_API_VERSIONS[0],
            ),
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.7),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        azure_endpoint = self.azure_endpoint
        azure_deployment = self.azure_deployment
        api_version = self.api_version
        api_key = self.api_key
        temperature = self.temperature
        max_tokens = self.max_tokens
        stream = self.stream

        try:
            output = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens or None,
                streaming=stream,
            )
        except Exception as e:
            msg = f"Could not connect to AzureOpenAI API: {e}"
            raise ValueError(msg) from e

        return output
