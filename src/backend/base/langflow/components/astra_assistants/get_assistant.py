from astra_assistants import patch  # type: ignore
from openai import OpenAI

from langflow.custom import Component
from langflow.inputs import MultilineInput, StrInput
from langflow.schema.message import Message
from langflow.template import Output


class AssistantsGetAssistantName(Component):
    display_name = "Get Assistant name"
    description = "Assistant by id"
    client = patch(OpenAI())

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
        assistant = self.client.beta.assistants.retrieve(
            assistant_id=self.assistant_id,
        )
        return Message(text=assistant.name)
