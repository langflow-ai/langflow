from langflow.base.astra_assistants.util import get_patched_openai_client
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs import MultilineInput, StrInput
from langflow.schema.message import Message
from langflow.template import Output


class AssistantsGetAssistantName(ComponentWithCache):
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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = get_patched_openai_client(self._shared_component_cache)

    def process_inputs(self) -> Message:
        assistant = self.client.beta.assistants.retrieve(
            assistant_id=self.assistant_id,
        )
        return Message(text=assistant.name)
