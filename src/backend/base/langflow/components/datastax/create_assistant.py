from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from loguru import logger

from langflow.base.astra_assistants.util import get_patched_openai_client
from langflow.inputs.inputs import MultilineInput, StrInput
from langflow.schema.message import Message
from langflow.template.field.base import Output


class AssistantsCreateAssistant(ComponentWithCache):
    icon = "AstraDB"
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
                "Models are supported via LiteLLM, "
                "see (https://docs.litellm.ai/docs/providers) for supported model names and env vars."
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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = get_patched_openai_client(self._shared_component_cache)

    def process_inputs(self) -> Message:
        logger.info(f"env_set is {self.env_set}")
        assistant = self.client.beta.assistants.create(
            name=self.assistant_name,
            instructions=self.instructions,
            model=self.model,
        )
        return Message(text=assistant.id)
