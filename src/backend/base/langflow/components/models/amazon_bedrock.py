from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.inputs.inputs import HandleInput
from langflow.io import DictInput, DropdownInput


class AmazonBedrockComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock"
    description: str = "Generate text using Amazon Bedrock LLMs."
    icon = "Amazon"
    name = "AmazonBedrockModel"

    inputs = [
        *LCModelComponent._base_inputs,
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
            info="List of available model IDs to choose from.",
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
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            is_list=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        MessageTextInput(
            name="endpoint_url",
            display_name="Endpoint URL",
            advanced=True,
            info="The URL of the Bedrock endpoint to use.",
        ),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_aws import ChatBedrock
        except ImportError as e:
            msg = "langchain_aws is not installed. Please install it with `pip install langchain_aws`."
            raise ImportError(msg) from e
        try:
            import boto3
        except ImportError as e:
            msg = "boto3 is not installed. Please install it with `pip install boto3`."
            raise ImportError(msg) from e
        if self.aws_access_key_id or self.aws_secret_access_key:
            try:
                session = boto3.Session(
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    aws_session_token=self.aws_session_token,
                )
            except Exception as e:
                msg = "Could not create a boto3 session."
                raise ValueError(msg) from e
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
        try:
            output = ChatBedrock(
                client=boto3_client,
                model_id=self.model_id,
                region_name=self.region_name,
                model_kwargs=self.model_kwargs,
                endpoint_url=self.endpoint_url,
                streaming=self.stream,
            )
        except Exception as e:
            msg = "Could not connect to AmazonBedrock API."
            raise ValueError(msg) from e
        return output
