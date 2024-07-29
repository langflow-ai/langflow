from astra_assistants import patch  # type: ignore
from langflow.custom import Component
from openai import OpenAI

from langflow.inputs import StrInput, MultilineInput
from langflow.schema.message import Message
from langflow.template import Output


class AssistantsGetAssistantName(Component):
    display_name = "Get Assistant name"
    description = "Assistant by id"

    inputs = [
        StrInput(
            name="assistant_id",
            display_name="Assistant ID",
            info="ID of the assistant",
        ),
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
        ),
    ]

    outputs = [
        Output(display_name="Assistant Name", name="assistant_name", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        patch(OpenAI())
        assistant = self.client.beta.assistants.retrieve(
            assistant_id=self.assistant_id,
        )
        message = Message(text=assistant.name)
        return message
