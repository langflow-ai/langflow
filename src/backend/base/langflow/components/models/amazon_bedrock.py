from typing import Any

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.inputs.inputs import HandleInput
from langflow.io import DictInput, DropdownInput
from langflow.schema.dotdict import dotdict


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
            value="",
            refresh_button=True,
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
        session = self.get_boto3_session()

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

    def get_boto3_session(self):
        try:
            import boto3
        except ImportError as e:
            msg = "boto3 is not installed. Please install it with `pip install boto3`."
            raise ImportError(msg) from e
        if self.aws_access_key_id or self.aws_secret_access_key:
            try:
                return boto3.Session(
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    aws_session_token=self.aws_session_token,
                )
            except Exception as e:
                msg = "Could not create a boto3 session."
                raise ValueError(msg) from e
        elif self.credentials_profile_name:
            return boto3.Session(profile_name=self.credentials_profile_name)
        else:
            return boto3.Session()

    def get_available_model_ids(self):
        session = self.get_boto3_session()
        client = session.client("bedrock", region_name=self.region_name)
        response = client.list_foundation_models()
        model_ids = [model["modelId"] for model in response["modelSummaries"]]
        print(model_ids)

        return [
            model_id for model_id in model_ids if self.check_model_access(client, model_id)
        ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "model_id":
            build_config["model_id"]["options"] = self.get_available_model_ids()
        return build_config

    def check_model_access(self, client, model_id):
        try:
            client.get_foundation_model(modelIdentifier=model_id)
            return True
        except client.exceptions.AccessDeniedException:
            return False
