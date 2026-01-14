from lfx.base.astra_assistants.util import get_patched_openai_client
from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.inputs.inputs import MultilineInput, StrInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class AssistantsGetAssistantName(ComponentWithCache):
    component_id: str = "d2af0887-9da6-46f1-bd75-24985b5e5761"
    display_name = "Get Assistant name"
    description = "Assistant by id"
    icon = "AstraDB"
    legacy = True
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
