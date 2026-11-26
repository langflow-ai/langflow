from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MultilineSecretInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class Dotenv(Component):
    display_name = "Dotenv"
    description = "Retired. Use Langflow global variables for flow configuration."
    icon = "AstraDB"
    legacy = True
    inputs = [
        MultilineSecretInput(
            name="dotenv_file_content",
            display_name="Dotenv file content",
            info="Paste the content of your .env file directly, since contents are sensitive, "
            "using a Global variable set as 'password' is recommended",
        )
    ]

    outputs = [
        Output(display_name="env_set", name="env_set", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        msg = "The Dotenv component has been retired. Replace it with Langflow global variables."
        raise ValueError(msg)
