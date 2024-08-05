from langchain_aws import ChatBedrock

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.io import DictInput, DropdownInput


class AmazonBedrockComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "Generate text using Amazon Bedrock LLMs."
    icon = "Amazon"
    name = "AmazonBedrockModel"

    inputs = LCModelComponent._base_inputs + [
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
        SecretStrInput(name="aws_access_key", display_name="Access Key"),
        SecretStrInput(name="aws_secret_key", display_name="Secret Key"),
        MessageTextInput(name="credentials_profile_name", display_name="Credentials Profile Name", advanced=True),
        MessageTextInput(name="region_name", display_name="Region Name", value="us-east-1"),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True, is_list=True),
        MessageTextInput(name="endpoint_url", display_name="Endpoint URL", advanced=True),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        if self.aws_access_key:
            import boto3  # type: ignore

            session = boto3.Session(
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
            )
        elif self.credentials_profile_name:
            import boto3

            session = boto3.Session(profile_name=self.credentials_profile_name)
        else:
            import boto3

            session = boto3.Session()

        client_params = {}
        if self.endpoint_url:
            client_params["endpoint_url"] = self.endpoint_url
        if self.region_name:
            client_params["region_name"] = self.region_name

        boto3_client = session.client("bedrock-runtime", **client_params)
        try:
            output = ChatBedrock(  # type: ignore
                client=boto3_client,
                model_id=self.model_id,
                region_name=self.region_name,
                model_kwargs=self.model_kwargs,
                endpoint_url=self.endpoint_url,
                streaming=self.stream,
            )
        except Exception as e:
            raise ValueError("Could not connect to AmazonBedrock API.") from e
        return output  # type: ignore
