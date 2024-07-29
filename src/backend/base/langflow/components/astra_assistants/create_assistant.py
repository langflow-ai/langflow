from astra_assistants import patch  # type: ignore
from openai import OpenAI
from langflow.custom import Component
from langflow.inputs import StrInput, MultilineInput
from langflow.template import Output
from langflow.schema.message import Message


class AssistantsCreateAssistant(Component):
    icon = "bot"
    display_name = "Create Assistant"
    description = "Creates an Assistant and returns it's id"

    inputs = [
        StrInput(
            name="assistant_name",
            display_name="Assistant Name",
            info="Name for the assistant being created",
        ),
        StrInput(
            name="instructions",
            display_name="Instructions",
            info="Instructions for the assistant, think of these as the system prompt.",
        ),
        StrInput(
            name="model",
            display_name="Model name",
            info=(
                "Model for the assistant.\n\n"
                "Environment variables for provider credentials can be set with the Dotenv Component.\n\n"
                "Models are supported via LiteLLM, see (https://docs.litellm.ai/docs/providers) for supported model names and env vars."
            ),
            # refresh_model=True
        ),
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
        ),
    ]

    outputs = [
        Output(display_name="Assistant ID", name="assistant_id", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        print(f"env_set is {self.env_set}")
        client = patch(OpenAI())
        assistant = client.beta.assistants.create(
            name=self.assistant_name,
            instructions=self.instructions,
            model=self.model,
        )
        message = Message(text=assistant.id)
        return message
