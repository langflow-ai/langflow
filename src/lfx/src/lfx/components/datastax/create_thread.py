from lfx.base.astra_assistants.util import get_patched_openai_client
from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.inputs.inputs import MultilineInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class AssistantsCreateThread(ComponentWithCache):
    display_name = "Create Assistant Thread"
    description = "Creates a thread and returns the thread id"
    icon = "AstraDB"
    legacy = True
    inputs = [
        MultilineInput(
            name="env_set",
            display_name="Environment Set",
            info="Dummy input to allow chaining with Dotenv Component.",
        ),
    ]

    outputs = [
        Output(display_name="Thread ID", name="thread_id", method="process_inputs"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = get_patched_openai_client(self._shared_component_cache)

    def process_inputs(self) -> Message:
        thread = self.client.beta.threads.create()
        thread_id = thread.id

        return Message(text=thread_id)
