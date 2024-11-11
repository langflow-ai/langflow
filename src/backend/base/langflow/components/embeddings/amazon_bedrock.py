from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.inputs import SecretStrInput
from langflow.io import DropdownInput, MessageTextInput, Output


class AmazonBedrockEmbeddingsComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock Embeddings"
    description: str = "Generate embeddings using Amazon Bedrock models."
    icon = "Amazon"
    name = "AmazonBedrockEmbeddings"

    inputs = [
        DropdownInput(
            name="model_id",
            display_name="Model Id",
            options=["amazon.titan-embed-text-v1"],
            value="amazon.titan-embed-text-v1",
        ),
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            info="The access key for your AWS account."
            "Usually set in Python code as the environment variable 'AWS_ACCESS_KEY_ID'.",
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Access Key",
            info="The secret key for your AWS account. "
            "Usually set in Python code as the environment variable 'AWS_SECRET_ACCESS_KEY'.",
        ),
        SecretStrInput(
            name="aws_session_token",
            display_name="AWS Session Token",
            advanced=True,
            info="The session key for your AWS account. "
            "Only needed for temporary credentials. "
            "Usually set in Python code as the environment variable 'AWS_SESSION_TOKEN'.",
        ),
        SecretStrInput(
            name="credentials_profile_name",
            display_name="Credentials Profile Name",
            advanced=True,
            info="The name of the profile to use from your "
            "~/.aws/credentials file. "
            "If not provided, the default profile will be used.",
        ),
        DropdownInput(
            name="region_name",
            display_name="Region Name",
            value="us-east-1",
            options=[
                "us-west-2",
                "us-west-1",
                "us-gov-west-1",
                "us-gov-east-1",
                "us-east-2",
                "us-east-1",
                "sa-east-1",
                "me-south-1",
                "me-central-1",
                "il-central-1",
                "eu-west-3",
                "eu-west-2",
                "eu-west-1",
                "eu-south-2",
                "eu-south-1",
                "eu-north-1",
                "eu-central-2",
                "eu-central-1",
                "cn-northwest-1",
                "cn-north-1",
                "ca-west-1",
                "ca-central-1",
                "ap-southeast-5",
                "ap-southeast-4",
                "ap-southeast-3",
                "ap-southeast-2",
                "ap-southeast-1",
                "ap-south-2",
                "ap-south-1",
                "ap-northeast-3",
                "ap-northeast-2",
                "ap-northeast-1",
                "ap-east-1",
                "af-south-1",
            ],
            info="The AWS region where your Bedrock resources are located.",
        ),
        MessageTextInput(
            name="endpoint_url",
            display_name="Endpoint URL",
            advanced=True,
            info="The URL of the AWS Bedrock endpoint to use.",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            from langchain_aws import BedrockEmbeddings
        except ImportError as e:
            msg = "langchain_aws is not installed. Please install it with `pip install langchain_aws`."
            raise ImportError(msg) from e
        try:
            import boto3
        except ImportError as e:
            msg = "boto3 is not installed. Please install it with `pip install boto3`."
            raise ImportError(msg) from e
        if self.aws_access_key_id or self.aws_secret_access_key:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=self.aws_session_token,
            )
        elif self.credentials_profile_name:
            session = boto3.Session(profile_name=self.credentials_profile_name)
        else:
            session = boto3.Session()

        client_params = {}
        if self.endpoint_url:
            client_params["endpoint_url"] = self.endpoint_url
        if self.region_name:
            client_params["region_name"] = self.region_name

        boto3_client = session.client("bedrock-runtime", **client_params)
        return BedrockEmbeddings(
            credentials_profile_name=self.credentials_profile_name,
            client=boto3_client,
            model_id=self.model_id,
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
        )
