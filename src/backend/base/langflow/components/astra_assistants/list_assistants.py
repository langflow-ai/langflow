from langflow.components.astra_assistants.util import get_patched_openai_client
from langflow.custom import Component
from langflow.schema.message import Message
from langflow.template.field.base import Output


class AssistantsListAssistants(Component):
    display_name = "List Assistants"
    description = "Returns a list of assistant id's"
    client = get_patched_openai_client()

    outputs = [
        Output(display_name="Assistants", name="assistants", method="process_inputs"),
    ]

    def process_inputs(self) -> Message:
        assistants = self.client.beta.assistants.list().data
        id_list = [assistant.id for assistant in assistants]
        return Message(
            # get text from list
            text="\n".join(id_list)
        )
