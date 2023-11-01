from typing import Optional
from langflow import CustomComponent
from langchain.llms.bedrock import Bedrock
from langchain.llms.base import BaseLLM


class AmazonBedrockComponent(CustomComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "LLM model from Amazon Bedrock."

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
            "code": {"show": False},
        }

    def build(
        self,
        model_id: str = "anthropic.claude-instant-v1",
        credentials_profile_name: Optional[str] = None,
    ) -> BaseLLM:
        try:
            output = Bedrock(
                credentials_profile_name=credentials_profile_name,
                model_id=model_id,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to AmazonBedrock API.") from e
        return output
