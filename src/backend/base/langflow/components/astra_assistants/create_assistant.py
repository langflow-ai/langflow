from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsCreateAssistant(CustomComponent):
    display_name = "Create Assistant"
    description = "Creates an Assistant and returns it's id"

    def build(self, name: str, instructions: str, model: str, env_set: str = None) -> str:
        print(f"env_set is {env_set}")
        if env_set is None:
            raise Exception("Environment variables not set")
        client = patch(OpenAI())
        assistant = client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=model,
        )
        return assistant.id
