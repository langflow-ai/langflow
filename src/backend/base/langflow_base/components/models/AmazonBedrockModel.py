from typing import Optional

from langchain_community.chat_models.bedrock import BedrockChat

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Text


class AmazonBedrockComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "Generate text using LLM model from Amazon Bedrock."
    icon = "Amazon"

    def build_config(self):
        return {
            "model_id": {
                "display_name": "Model Id",
                "options": [
                    "ai21.j2-grande-instruct",
                    "ai21.j2-jumbo-instruct",
                    "ai21.j2-mid",
                    "ai21.j2-mid-v1",
                    "ai21.j2-ultra",
                    "ai21.j2-ultra-v1",
                    "anthropic.claude-instant-v1",
                    "anthropic.claude-v1",
                    "anthropic.claude-v2",
                    "cohere.command-text-v14",
                ],
            },
            "credentials_profile_name": {"display_name": "Credentials Profile Name"},
            "streaming": {"display_name": "Streaming", "field_type": "bool"},
            "endpoint_url": {"display_name": "Endpoint URL"},
            "region_name": {"display_name": "Region Name"},
            "model_kwargs": {"display_name": "Model Kwargs"},
            "cache": {"display_name": "Cache"},
            "code": {"advanced": True},
            "input_value": {"display_name": "Input"},
            "system_message": {"display_name": "System Message", "info": "System message to pass to the model."},
            "stream": {
                "display_name": "Stream",
                "info": "Stream the response from the model.",
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
        streaming: bool = False,
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
                streaming=streaming,
                cache=cache,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to AmazonBedrock API.") from e

        return self.get_chat_result(output, stream, input_value, system_message)
