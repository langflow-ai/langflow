from typing import TYPE_CHECKING, Optional

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.field_typing import Text
from langflow.schema.schema import Record

if TYPE_CHECKING:
    from zep_python.langchain import ZepChatMessageHistory


class ZepMessageWriterComponent(BaseMemoryComponent):
    display_name = "Zep Message Writer"
    description = "Writes a message to Zep."

    def build_config(self):
        return {
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "url": {
                "display_name": "Zep URL",
                "info": "URL of the Zep instance.",
                "input_types": ["Text"],
            },
            "api_key": {
                "display_name": "Zep API Key",
                "info": "API Key for the Zep instance.",
                "password": True,
            },
            "limit": {
                "display_name": "Limit",
                "info": "Limit of search results.",
                "advanced": True,
            },
            "input_value": {
                "display_name": "Input Record",
                "info": "Record to write to Zep.",
            },
            "api_base_path": {
                "display_name": "API Base Path",
                "options": ["api/v1", "api/v2"],
            },
        }

    def add_message(
        self, sender: Text, sender_name: Text, text: Text, session_id: Text, metadata: dict | None = None, **kwargs
    ):
        """
        Adds a message to the ZepChatMessageHistory memory.

        Args:
            sender (Text): The type of the message sender. Valid values are "Machine" or "User".
            sender_name (Text): The name of the message sender.
            text (Text): The content of the message.
            session_id (Text): The session ID associated with the message.
            metadata (dict | None, optional): Additional metadata for the message. Defaults to None.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If the ZepChatMessageHistory instance is not provided.

        """
        memory: ZepChatMessageHistory | None = kwargs.pop("memory", None)
        if memory is None:
            raise ValueError("ZepChatMessageHistory instance is required.")
        if metadata is None:
            metadata = {}
        metadata["sender_name"] = sender_name
        metadata.update(kwargs)
        if sender == "Machine":
            memory.add_ai_message(text, metadata=metadata)
        elif sender == "User":
            memory.add_user_message(text, metadata=metadata)
        else:
            raise ValueError(f"Invalid sender type: {sender}")

    def build(
        self,
        input_value: Record,
        session_id: Text,
        api_base_path: str = "api/v1",
        url: Optional[Text] = None,
        api_key: Optional[Text] = None,
    ) -> Record:
        try:
            # Monkeypatch API_BASE_PATH to
            # avoid 404
            # This is a workaround for the local Zep instance
            # cloud Zep works with v2
            import zep_python.zep_client
            from zep_python import ZepClient
            from zep_python.langchain import ZepChatMessageHistory

            zep_python.zep_client.API_BASE_PATH = api_base_path
        except ImportError:
            raise ImportError(
                "Could not import zep-python package. " "Please install it with `pip install zep-python`."
            )
        if url == "":
            url = None

        zep_client = ZepClient(api_url=url, api_key=api_key)
        memory = ZepChatMessageHistory(session_id=session_id, zep_client=zep_client)
        self.add_message(**input_value.data, memory=memory)
        self.status = f"Added message to Zep memory for session {session_id}"
        return input_value
