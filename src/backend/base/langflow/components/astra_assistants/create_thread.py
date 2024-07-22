from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsCreateThread(CustomComponent):
    display_name = "Create Assistant Thread"
    description = "Creates a thread and returns the thread id"

    def build_config(self):
        return {
            "env_set": {
                "display_name": "Environment Set",
                "advanced": False,
                "info": "Dummy input to allow chaining with Dotenv Component.",
            },
        }

    def build(self, env_set: str = None) -> str:
        client = patch(OpenAI())

        thread = client.beta.threads.create()
        thread_id = thread.id

        return thread_id
