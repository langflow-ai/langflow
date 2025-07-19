import os

from lfx.custom.custom_component.component import Component

from langflow.inputs.inputs import StrInput
from langflow.schema.message import Message
from langflow.template.field.base import Output


class GetEnvVar(Component):
    display_name = "Get env var"
    description = "Get env var"
    icon = "AstraDB"

    inputs = [
        StrInput(
            name="env_var_name",
            display_name="Env var name",
            info="Name of the environment variable to get",
        )
    ]

    outputs = [
        Output(display_name="Env var value", name="env_var_value", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        if self.env_var_name not in os.environ:
            msg = f"Environment variable {self.env_var_name} not set"
            raise ValueError(msg)
        return Message(text=os.environ[self.env_var_name])
