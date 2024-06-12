from typing import Optional

from langchain_openai import AzureChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text, BaseLanguageModel
from langflow.template import Input, Output


class AzureChatOpenAIComponent(LCModelComponent):
    display_name: str = "Azure OpenAI"
    description: str = "Generate text using Azure OpenAI LLMs."
    documentation: str = "https://python.langchain.com/docs/integrations/llms/azure_openai"
    beta = False
    icon = "Azure"

    AZURE_OPENAI_MODELS = [
        "gpt-35-turbo",
        "gpt-35-turbo-16k",
        "gpt-35-turbo-instruct",
        "gpt-4",
        "gpt-4-32k",
        "gpt-4-vision",
    ]

    AZURE_OPENAI_API_VERSIONS = [
        "2023-03-15-preview",
        "2023-05-15",
        "2023-06-01-preview",
        "2023-07-01-preview",
        "2023-08-01-preview",
        "2023-09-01-preview",
        "2023-12-01-preview",
    ]

    inputs = [
        Input(
            name="model", type=str, display_name="Model Name", options=AZURE_OPENAI_MODELS, value=AZURE_OPENAI_MODELS[0]
        ),
        Input(
            name="azure_endpoint",
            type=str,
            display_name="Azure Endpoint",
            info="Your Azure endpoint, including the resource.. Example: `https://example-resource.azure.openai.com/`",
        ),
        Input(name="azure_deployment", type=str, display_name="Deployment Name"),
        Input(
            name="api_version",
            type=str,
            display_name="API Version",
            options=AZURE_OPENAI_API_VERSIONS,
            value=AZURE_OPENAI_API_VERSIONS[-1],
            advanced=True,
        ),
        Input(name="api_key", type=str, display_name="API Key", password=True),
        Input(name="temperature", type=float, display_name="Temperature", default=0.7),
        Input(
            name="max_tokens",
            type=Optional[int],
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        Input(name="input_value", type=str, display_name="Input", input_types=["Text", "Record", "Prompt"]),
        Input(name="stream", type=bool, display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        Input(
            name="system_message",
            type=Optional[str],
            display_name="System Message",
            advanced=True,
            info="System message to pass to the model.",
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="model_response"),
    ]

    def text_response(self) -> Text:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.model_response()
        result = self.get_chat_result(output, stream, input_value, system_message)
        self.status = result
        return result

    def model_response(self) -> BaseLanguageModel:
        model = self.model
        azure_endpoint = self.azure_endpoint
        azure_deployment = self.azure_deployment
        api_version = self.api_version
        api_key = self.api_key
        temperature = self.temperature
        max_tokens = self.max_tokens
        stream = self.stream

        if api_key:
            secret_api_key = SecretStr(api_key)
        else:
            secret_api_key = None

        try:
            output = AzureChatOpenAI(
                model=model,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
                api_key=secret_api_key,
                temperature=temperature,
                max_tokens=max_tokens or None,
                streaming=stream,
            )
        except Exception as e:
            raise ValueError("Could not connect to AzureOpenAI API.") from e

        return output
