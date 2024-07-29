import io
from dotenv import load_dotenv
from langflow.custom import Component
from langflow.inputs import MultilineSecretInput
from langflow.schema.message import Message
from langflow.template import Output


class Dotenv(Component):
    display_name = "Dotenv"
    description = "Load .env file into env vars"

    inputs = [
        MultilineSecretInput(
            name="dotenv_file_content",
            display_name="Dotenv file content",
            info="Paste the content of your .env file directly, since contents are sensitive, using a Global variable set as 'password' is recommended",
        )
    ]

    outputs = [
        Output(display_name="env_set", name="env_set", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        fake_file = io.StringIO(self.dotenv_file_content)
        result = load_dotenv(stream=fake_file, override=True)

        message = Message(text="No variables found in .env")
        if result:
            message = Message(text="Loaded .env")
        return message
