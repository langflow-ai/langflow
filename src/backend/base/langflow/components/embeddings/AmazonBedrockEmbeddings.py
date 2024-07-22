from langchain_community.embeddings import BedrockEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
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
        MessageTextInput(
            name="credentials_profile_name",
            display_name="Credentials Profile Name",
        ),
        MessageTextInput(
            name="endpoint_url",
            display_name="Bedrock Endpoint URL",
        ),
        MessageTextInput(
            name="region_name",
            display_name="AWS Region",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            output = BedrockEmbeddings(
                credentials_profile_name=self.credentials_profile_name,
                model_id=self.model_id,
                endpoint_url=self.endpoint_url,
                region_name=self.region_name,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to Amazon Bedrock API.") from e
        return output
