from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsCreateAssistant(CustomComponent):
    display_name = "Create Assistant"
    description = "Creates an Assistant and returns it's id"

    def build_config(self):
        return {
            "name": {
                "display_name": "Assistant Name",
                "advanced": False,
                "info": "Name for the assistant being created",
            },
            "instructions": {
                "display_name": "Instructions",
                "info": "Instructions for the assistant, think of these as the system prompt.",
                "advanced": False,
            },
            "model": {
                "display_name": "Model name",
                "advanced": False,
                "info": (
                    "Model for the assistant.\n\n"
                    "Environment variables for provider credentials can be set with the Dotenv Component.\n\n"
                    "Models are supported via LiteLLM, see (https://docs.litellm.ai/docs/providers) for supported model names and env vars."
                ),
            },
            "env_set": {
                "display_name": "Environment Set",
                "advanced": False,
                "info": "Dummy input to allow chaining with Dotenv Component.",
            },
        }

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
