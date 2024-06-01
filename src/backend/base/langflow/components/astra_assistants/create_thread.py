from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsCreateThread(CustomComponent):
    display_name = "Create Thread"
    description = "Creates a thread"

    def build(self, env_set: str = None) -> str:
        client = patch(OpenAI())

        thread = client.beta.threads.create()
        thread_id = thread.id

        return thread_id
