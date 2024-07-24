from typing import Optional
from astra_assistants import patch  # type: ignore
from openai import OpenAI
from openai.lib.streaming import AssistantEventHandler

from langflow.custom import CustomComponent


class AssistantsRun(CustomComponent):
    display_name = "Run Assistant"
    description = "Executes an Assistant Run against a thread"

    def build_config(self):
        return {
            "assistant_id": {
                "display_name": "Assistant ID",
                "advanced": False,
                "info": (
                    "The ID of the assistant to run. \n\n"
                    "Can be retrieved using the List Assistants component or created with the Create Assistant component."
                ),
            },
            "user_message": {
                "display_name": "User Message",
                "info": "User message to pass to the run.",
                "advanced": False,
            },
            "thread_id": {
                "display_name": "Thread ID",
                "advanced": False,
                "info": "Thread ID to use with the run. If not provided, a new thread will be created.",
            },
            "env_set": {
                "display_name": "Environment Set",
                "advanced": False,
                "info": "Dummy input to allow chaining with Dotenv Component.",
            },
        }

    def build(
        self, assistant_id: str, user_message: str, thread_id: Optional[str] = None, env_set: Optional[str] = None
    ) -> str:
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
