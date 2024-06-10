from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsGetAssistantName(CustomComponent):
    display_name = "Get Assistant name"
    description = "Assistant by id"

    def build_config(self):
        return {
            "assistant_id": {
                "display_name": "Assistant ID",
                "advanced": False,
            },
            "env_set": {
                "display_name": "Environment Set",
                "advanced": False,
                "info": "Dummy input to allow chaining with Dotenv Component.",
            },
        }

    def build(self, assistant_id: str, env_set: str = None) -> str:
        client = patch(OpenAI())
        assistant = client.beta.assistants.retrieve(
            assistant_id=assistant_id,
        )
        return assistant.name
