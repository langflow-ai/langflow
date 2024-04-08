from typing import Optional
from langflow.field_typing import BaseLanguageModel
from langchain_community.llms.bedrock import Bedrock

from langflow.interface.custom.custom_component import CustomComponent


class AmazonBedrockComponent(CustomComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "LLM model from Amazon Bedrock."
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
        }

    def build(
        self,
        model_id: str = "anthropic.claude-instant-v1",
        credentials_profile_name: Optional[str] = None,
        region_name: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        endpoint_url: Optional[str] = None,
        streaming: bool = False,
        cache: Optional[bool] = None,
    ) -> BaseLanguageModel:
        try:
            output = Bedrock(
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
        return output
