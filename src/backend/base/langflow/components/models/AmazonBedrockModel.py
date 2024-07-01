from langchain_aws import ChatBedrock

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import BoolInput, DictInput, DropdownInput, MessageInput, Output, StrInput


class AmazonBedrockComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "Generate text using Amazon Bedrock LLMs."
    icon = "Amazon"

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        DropdownInput(
            name="model_id",
            display_name="Model ID",
            options=[
                "amazon.titan-text-express-v1",
                "amazon.titan-text-lite-v1",
                "amazon.titan-text-premier-v1:0",
                "amazon.titan-embed-text-v1",
                "amazon.titan-embed-text-v2:0",
                "amazon.titan-embed-image-v1",
                "amazon.titan-image-generator-v1",
                "anthropic.claude-v2",
                "anthropic.claude-v2:1",
                "anthropic.claude-3-sonnet-20240229-v1:0",
                "anthropic.claude-3-haiku-20240307-v1:0",
                "anthropic.claude-3-opus-20240229-v1:0",
                "anthropic.claude-instant-v1",
                "ai21.j2-mid-v1",
                "ai21.j2-ultra-v1",
                "cohere.command-text-v14",
                "cohere.command-light-text-v14",
                "cohere.command-r-v1:0",
                "cohere.command-r-plus-v1:0",
                "cohere.embed-english-v3",
                "cohere.embed-multilingual-v3",
                "meta.llama2-13b-chat-v1",
                "meta.llama2-70b-chat-v1",
                "meta.llama3-8b-instruct-v1:0",
                "meta.llama3-70b-instruct-v1:0",
                "mistral.mistral-7b-instruct-v0:2",
                "mistral.mixtral-8x7b-instruct-v0:1",
                "mistral.mistral-large-2402-v1:0",
                "mistral.mistral-small-2402-v1:0",
                "stability.stable-diffusion-xl-v0",
                "stability.stable-diffusion-xl-v1",
            ],
            value="anthropic.claude-3-haiku-20240307-v1:0",
        ),
        StrInput(name="credentials_profile_name", display_name="Credentials Profile Name"),
        StrInput(name="region_name", display_name="Region Name"),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        StrInput(name="endpoint_url", display_name="Endpoint URL"),
        BoolInput(name="cache", display_name="Cache"),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        model_id = self.model_id
        credentials_profile_name = self.credentials_profile_name
        region_name = self.region_name
        model_kwargs = self.model_kwargs
        endpoint_url = self.endpoint_url
        cache = self.cache
        stream = self.stream
        try:
            output = ChatBedrock(  # type: ignore
                credentials_profile_name=credentials_profile_name,
                model_id=model_id,
                region_name=region_name,
                model_kwargs=model_kwargs,
                endpoint_url=endpoint_url,
                streaming=stream,
                cache=cache,
            )
        except Exception as e:
            raise ValueError("Could not connect to AmazonBedrock API.") from e
        return output  # type: ignore
