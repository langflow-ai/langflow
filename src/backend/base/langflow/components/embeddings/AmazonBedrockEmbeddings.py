from langchain_community.embeddings import BedrockEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.inputs import SecretStrInput
from langflow.io import DropdownInput, MessageTextInput, Output


class AmazonBedrockEmbeddingsComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock Embeddings"
    description: str = "Generate embeddings using Amazon Bedrock models."
    documentation = "https://python.langchain.com/docs/modules/data_connection/text_embedding/integrations/bedrock"
    icon = "Amazon"
    name = "AmazonBedrockEmbeddings"

    inputs = [
        DropdownInput(
            name="model_id",
            display_name="Model Id",
            options=["amazon.titan-embed-text-v1"],
            value="amazon.titan-embed-text-v1",
        ),
        SecretStrInput(name="aws_access_key", display_name="Access Key"),
        SecretStrInput(name="aws_secret_key", display_name="Secret Key"),
        MessageTextInput(
            name="credentials_profile_name",
            display_name="Credentials Profile Name",
            advanced=True,
        ),
        MessageTextInput(name="region_name", display_name="Region Name", value="us-east-1"),
        MessageTextInput(name="endpoint_url", display_name=" Endpoint URL", advanced=True),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
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
        output = BedrockEmbeddings(
            credentials_profile_name=self.credentials_profile_name,
            client=boto3_client,
            model_id=self.model_id,
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
        )  # type: ignore
        return output
