import re
from typing import TYPE_CHECKING, Any

import aiofiles

from lfx.base.models.aws_constants import AWS_REGIONS
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    FileInput,
    FloatInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    Output,
    SecretStrInput,
)
from lfx.schema.data import Data

MAX_DOC_LENGTH = 1000  # Maximum length for documentation strings


class AWSAPICallComponent(Component):
    """A component that can dynamically determine fields for a specific service method
    and execute the AWS API call within a flow.
    """

    display_name: str = "AWS API Call"
    description: str = "Makes an API call to an AWS service."
    icon: str = "Amazon"
    name: str = "AWSAPICall"

    inputs = [
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            info="The access key for your AWS account."
            "Usually set in Python code as the environment variable 'AWS_ACCESS_KEY_ID'.",
            required=True,
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Access Key",
            info="The secret key for your AWS account. "
            "Usually set in Python code as the environment variable 'AWS_SECRET_ACCESS_KEY'.",
            required=True,
        ),
        SecretStrInput(
            name="aws_session_token",
            display_name="AWS Session Token",
            advanced=False,
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
            options=AWS_REGIONS,
            info="The AWS region to execute the call in.",
        ),
        MessageTextInput(
            name="endpoint_url",
            display_name="Endpoint URL",
            advanced=True,
            info="The URL of the AWS endpoint to use.",
        ),
        DropdownInput(
            name="aws_service",
            display_name="Service",
            real_time_refresh=True,
            refresh_button=True,
            options=[""],
            info="The AWS service to make a call to.",
            required=True,
        ),
        DropdownInput(
            name="aws_method",
            display_name="Method",
            real_time_refresh=True,
            refresh_button=True,
            options=[""],
            info="The AWS method to make a call to.",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="execute_call"),
    ]

    def _get_session(self) -> Any:
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

        return session

    def _get_client(self, session) -> Any:
        client_params = {}
        if self.endpoint_url:
            client_params["endpoint_url"] = self.endpoint_url
        if self.region_name:
            client_params["region_name"] = self.region_name

        return session.client(self.aws_service, **client_params)

    def update_build_config(self, build_config: dict, _: str, field_name: str | None = None) -> dict:
        session = self._get_session()
        build_config["aws_service"]["options"] = session.get_available_services()

        if self.aws_service and self.aws_service != "":
            client = self._get_client(session)
            build_config["aws_method"]["options"] = list(client._service_model.operation_names)

        if field_name == "aws_method":
            # dynamically add top-level parameters
            for key in list(build_config.keys()):
                if key.startswith("method_field_") or key.startswith("method_filefield_"):
                    del build_config[key]

            params = []

            try:
                if TYPE_CHECKING:
                    from botocore.model import Shape
            except ImportError as e:
                msg = "boto3 or botocore is not installed. Please install it with `pip install boto3`."
                raise ImportError(msg) from e

            client = self._get_client(session)
            operation_model = client._service_model.operation_model(self.aws_method)

            input_shape: Shape = operation_model.input_shape
            if input_shape is not None:
                members = input_shape.members
                required = set(input_shape.required_members)

                for name, shape in members.items():
                    doc = re.sub(r"<.*?>", "", shape.documentation) if hasattr(shape, "documentation") else ""
                    if len(doc) > MAX_DOC_LENGTH:
                        doc = doc[:MAX_DOC_LENGTH] + "..."

                    params.append(
                        {
                            "name": name,
                            "type": shape.type_name,
                            "required": name in required,
                            "sensitive": shape.sensitive if hasattr(shape, "sensitive") else False,
                            "description": doc,
                        }
                    )

            for param in params:
                if param["type"] == "string":
                    field = MessageInput(
                        display_name=param["name"],
                        name="method_field_" + param["name"],
                        info=param["description"],
                        required=param["required"],
                        advanced=not param["required"],
                    )
                    if param["sensitive"]:
                        field = SecretStrInput(
                            display_name=param["name"],
                            name="method_field_" + param["name"],
                            info=param["description"],
                            required=param["required"],
                            advanced=not param["required"],
                        )
                    build_config["method_field_" + param["name"]] = field.to_dict()
                elif param["type"] == "boolean":
                    field = BoolInput(
                        display_name=param["name"],
                        name="method_field_" + param["name"],
                        info=param["description"],
                        required=param["required"],
                        advanced=not param["required"],
                    )
                    build_config["method_field_" + param["name"]] = field.to_dict()
                elif param["type"] == "blob":
                    field = FileInput(
                        display_name=param["name"],
                        name="method_filefield_" + param["name"],
                        info=param["description"],
                        required=param["required"],
                        advanced=not param["required"],
                        file_types=[
                            "txt",
                            "json",
                            "jpg",
                            "png",
                        ],  # TODO: fix me to support all types - https://github.com/langflow-ai/langflow/issues/9933
                    )
                    build_config["method_filefield_" + param["name"]] = field.to_dict()
                elif param["type"] == "integer" or param["type"] == "long":
                    field = IntInput(
                        display_name=param["name"],
                        name="method_field_" + param["name"],
                        info=param["description"],
                        required=param["required"],
                        advanced=not param["required"],
                    )
                    build_config["method_field_" + param["name"]] = field.to_dict()
                elif param["type"] == "double":
                    field = FloatInput(
                        display_name=param["name"],
                        name="method_field_" + param["name"],
                        info=param["description"],
                        required=param["required"],
                        advanced=not param["required"],
                    )
                    build_config["method_field_" + param["name"]] = field.to_dict()
                elif param["type"] == "timestamp":
                    field = FloatInput(
                        display_name=param["name"],
                        name="method_field_" + param["name"],
                        info=param["description"] + "\n\nThis accepts a timestamp as epoch.",
                        required=param["required"],
                        advanced=not param["required"],
                    )
                    build_config["method_field_" + param["name"]] = field.to_dict()
                elif param["type"] == "structure" or param["type"] == "map" or param["type"] == "list":
                    field = DataInput(
                        display_name=param["name"],
                        name="method_field_" + param["name"],
                        info=param["description"]
                        + "\n\nAccepts JSON Data as parameters input. Uses boto3-conformant parameters.",
                        required=param["required"],
                        advanced=not param["required"],
                    )
                    build_config["method_field_" + param["name"]] = field.to_dict()

        return build_config

    async def execute_call(self) -> Data:
        session = self._get_session()
        client = self._get_client(session)

        try:
            from botocore import xform_name  # this_type_of_casing function

            if TYPE_CHECKING:
                from botocore.model import Shape
        except ImportError as e:
            msg = "botocore is not installed. Please install it with `pip install botocore`."
            raise ImportError(msg) from e
        method = getattr(client, xform_name(self.aws_method))

        # retrieve for method
        params = []

        client = self._get_client(session)
        operation_model = client._service_model.operation_model(self.aws_method)

        input_shape: Shape = operation_model.input_shape
        if input_shape is not None:
            members = input_shape.members
            required = set(input_shape.required_members)

            for name, shape in members.items():
                doc = re.sub(r"<.*?>", "", shape.documentation) if hasattr(shape, "documentation") else ""
                if len(doc) > MAX_DOC_LENGTH:
                    doc = doc[:MAX_DOC_LENGTH] + "..."

                params.append(
                    {
                        "name": name,
                        "type": shape.type_name,
                        "required": name in required,
                        "sensitive": shape.sensitive if hasattr(shape, "sensitive") else False,
                        "description": doc,
                    }
                )

        returns = {}
        for param in params:
            param_name = param["name"]
            if hasattr(self, "method_field_" + param_name):
                field_value = getattr(self, "method_field_" + param_name)
                if field_value is not None:
                    if isinstance(field_value, bool):
                        if field_value:
                            returns[param_name] = True
                    elif isinstance(field_value, (int, float)):
                        returns[param_name] = field_value
                    elif hasattr(field_value, "text"):
                        returns[param_name] = field_value.text
                    elif hasattr(field_value, "data"):
                        returns[param_name] = field_value.data
                    elif isinstance(field_value, str):
                        if field_value != "":
                            returns[param_name] = field_value
                    else:
                        msg = f"Unsupported type for parameter '{param_name}': {type(field_value)}"
                        raise ValueError(msg)
            elif hasattr(self, "method_filefield_" + param_name):
                field_value = getattr(self, "method_filefield_" + param_name)
                if field_value is not None and field_value != "":
                    async with aiofiles.open(str(field_value), "rb") as f:
                        returns[param_name] = await f.read()

        result = method(**returns)

        return Data(text=str(result), data=result)
