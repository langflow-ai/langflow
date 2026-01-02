from lfx.base.astra_assistants.util import get_patched_openai_client
from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.schema.message import Message
from lfx.template.field.base import Output


class AssistantsListAssistants(ComponentWithCache):
    display_name = "List Assistants"
    description = "Returns a list of assistant id's"
    icon = "AstraDB"
    legacy = True
    outputs = [
        Output(display_name="Assistants", name="assistants", method="process_inputs"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = get_patched_openai_client(self._shared_component_cache)

    def process_inputs(self) -> Message:
        assistants = self.client.beta.assistants.list().data
        id_list = [assistant.id for assistant in assistants]
        return Message(
            # get text from list
            text="\n".join(id_list)
        )
