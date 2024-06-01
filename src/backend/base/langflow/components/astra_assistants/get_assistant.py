from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsGetAssistantName(CustomComponent):
    display_name = "Get Assistant name"
    description = "Assistant by id"

    def build(self, assistant_id: str, env_set: str = None) -> str:
        client = patch(OpenAI())
        assistant = client.beta.assistants.retrieve(
            assistant_id=assistant_id,
        )
        return assistant.name
