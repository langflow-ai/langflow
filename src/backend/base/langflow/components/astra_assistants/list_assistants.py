from typing import List
from langflow.custom import CustomComponent
from openai import OpenAI
from astra_assistants import patch


class AssistantsListAssistants(CustomComponent):
    display_name = "List Assistants"
    description = "Returns a list of assistant id's"

    def build(self) -> List[str]:
        client = patch(OpenAI())
        assistants = client.beta.assistants.list()
        id_list = [assistant.id for assistant in assistants]
        return id_list
