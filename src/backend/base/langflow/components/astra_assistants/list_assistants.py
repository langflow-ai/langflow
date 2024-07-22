from typing import List

from astra_assistants import patch  # type: ignore
from openai import OpenAI

from langflow.custom import CustomComponent


class AssistantsListAssistants(CustomComponent):
    display_name = "List Assistants"
    description = "Returns a list of assistant id's"

    def build_config(self):
        return {}

    def build(self) -> List[str]:
        client = patch(OpenAI())
        assistants = client.beta.assistants.list()
        id_list = [assistant.id for assistant in assistants]
        return id_list
