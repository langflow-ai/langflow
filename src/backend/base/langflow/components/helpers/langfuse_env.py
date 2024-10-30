import os

from langflow.custom import Component
from langflow.io import Output,SecretStrInput
from langflow.schema import Data


class EnvVarSetter(Component):
    display_name = " Langfuse Environment Variable Setter"
    description = "Sets multiple environment variables related to Langfuse."
    documentation: str = "http://docs.langflow.org/components/env-var-setter"
    icon = "settings"
    name = "Langfuse EnvVarSetter"

    inputs = [
        SecretStrInput(
            name="secretkey",
            display_name="Langfuse Secret Key",
            info="Secret key for accessing Langfuse.",
            value="LANGFUSE_SECRET_KEY",
            required=True,
        ),
        SecretStrInput(
            name="publickey",
            display_name="Langfuse Public Key",
            info="Public key for accessing Langfuse.",
            value="LANGFUSE_PUBLIC_KEY",
            required=True,
        ),
        SecretStrInput(
            name="host",
            display_name="Langfuse Host",
            info="Host for accessing Langfuse.",
            value="LANGFUSE_HOST",
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Success Message",
            name="success_message",
            method="build_output",
        ),
    ]

    def build_output(self) -> Data:
        # Set environment variables
        os.environ["LANGFUSE_SECRET_KEY"] = self.secretkey
        os.environ["LANGFUSE_PUBLIC_KEY"] = self.publickey
        os.environ["LANGFUSE_HOST"] = self.host

        success_message = "Environment variables set successfully"

        data = Data(value=success_message)
        self.status = data
        return data
