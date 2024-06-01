from langflow.custom import CustomComponent
from openai import OpenAI
from openai.lib.streaming import AssistantEventHandler
from astra_assistants import patch


class AssistantsRun(CustomComponent):
    display_name = "Assistant Run"
    description = "Executes an Assistant Run against a thread"

    def build(self, assistant_id: str, user_message: str, thread_id: str = None, env_set: str = None) -> str:
        text = ""
        client = patch(OpenAI())

        if thread_id is None:
            thread = client.beta.threads.create()
            thread_id = thread.id

        # add the user message
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=user_message)

        class EventHandler(AssistantEventHandler):
            def __init__(self):
                super().__init__()

        event_handler = EventHandler()
        with client.beta.threads.runs.create_and_stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            event_handler=event_handler,
        ) as stream:
            # return stream.text_deltas
            for part in stream.text_deltas:
                text += part
                print(part)
        return text
