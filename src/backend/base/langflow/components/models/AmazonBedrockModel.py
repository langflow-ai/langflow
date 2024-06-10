from typing import Optional

from langchain_community.chat_models.bedrock import BedrockChat

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class AmazonBedrockComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "Generate text using Amazon Bedrock LLMs."
    icon = "Amazon"
    field_order = [
        "model_id",
        "credentials_profile_name",
        "region_name",
        "model_kwargs",
        "endpoint_url",
        "cache",
        "stream",
        "input_value",
        "system_message",
    ]

    def build_config(self):
        return {
            "model_id": {
                "display_name": "Model Id",
                "options": [
                    "amazon.titan-text-express-v1",
                    "amazon.titan-text-lite-v1",
                    "amazon.titan-embed-text-v1",
                    "amazon.titan-embed-image-v1",
                    "amazon.titan-image-generator-v1",
                    "anthropic.claude-v2",
                    "anthropic.claude-v2:1",
                    "anthropic.claude-3-sonnet-20240229-v1:0",
                    "anthropic.claude-3-haiku-20240307-v1:0",
                    "anthropic.claude-instant-v1",
                    "ai21.j2-mid-v1",
                    "ai21.j2-ultra-v1",
                    "cohere.command-text-v14",
                    "cohere.command-light-text-v14",
                    "cohere.embed-english-v3",
                    "cohere.embed-multilingual-v3",
                    "meta.llama2-13b-chat-v1",
                    "meta.llama2-70b-chat-v1",
                    "mistral.mistral-7b-instruct-v0:2",
                    "mistral.mixtral-8x7b-instruct-v0:1",
                ],
            },
            "credentials_profile_name": {"display_name": "Credentials Profile Name"},
            "endpoint_url": {"display_name": "Endpoint URL"},
            "region_name": {"display_name": "Region Name"},
            "model_kwargs": {
                "display_name": "Model Kwargs",
                "advanced": True,
            },
            "cache": {"display_name": "Cache"},
            "input_value": {"display_name": "Input", "input_types": ["Text", "Record", "Prompt"]},
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "advanced": True,
            },
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Text,
        system_message: Optional[str] = None,
        model_id: str = "anthropic.claude-instant-v1",
        credentials_profile_name: Optional[str] = None,
        region_name: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        endpoint_url: Optional[str] = None,
        cache: Optional[bool] = None,
        stream: bool = False,
    ) -> Text:
        try:
            output = BedrockChat(
                credentials_profile_name=credentials_profile_name,
                model_id=model_id,
                region_name=region_name,
                model_kwargs=model_kwargs,
                endpoint_url=endpoint_url,
                streaming=stream,
                cache=cache,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to AmazonBedrock API.") from e

        return self.get_chat_result(output, stream, input_value, system_message)
