from astra_assistants import patch  # type: ignore
from openai import OpenAI

from langflow.custom import Component
from langflow.inputs import MultilineInput
from langflow.schema.message import Message
from langflow.template import Output


class AssistantsCreateThread(Component):
    display_name = "Create Assistant Thread"
    description = "Creates a thread and returns the thread id"
    client = patch(OpenAI())

    inputs = [
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
        ),
    ]

    outputs = [
        Output(display_name="Thread ID", name="thread_id", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        thread = self.client.beta.threads.create()
        thread_id = thread.id

        return Message(text=thread_id)
