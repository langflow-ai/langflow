from typing import TYPE_CHECKING, Optional

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.field_typing import Text
from langflow.schema.schema import Record

from langchain_community.chat_message_histories.astradb import AstraDBChatMessageHistory

if TYPE_CHECKING:
    import astrapy


class AstraDBMessageWriterComponent(BaseMemoryComponent):
    display_name = "Astra DB Message Writer"
    description = "Writes a message to Astra DB."

    def build_config(self):
        return {
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "token": {
                "display_name": "Astra DB Application Token",
                "info": "Token for the Astra DB instance.",
                "password": True,
            },
            "api_endpoint": {
                "display_name": "Astra DB API Endpoint",
                "info": "API Endpoint for the Astra DB instance.",
                "password": True,
            },
            "limit": {
                "display_name": "Limit",
                "info": "Limit of search results.",
                "advanced": True,
            },
            "input_value": {
                "display_name": "Input Record",
                "info": "Record to write to Astra DB.",
            },
        }

    def add_message(
        self, text: Text, **kwargs
    ):
        """
        Adds a message to the AstraDBChatMessageHistory memory.

        Args:
            text (Text): The content of the message.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If the AstraDBChatMessageHistory instance is not provided.

        """
        memory: AstraDBChatMessageHistory | None = kwargs.pop("memory", None)
        if memory is None:
            raise ValueError("AstraDBChatMessageHistory instance is required.")

        memory.add_messages([text])

    def build(
        self,
        input_value: Record,
        session_id: Text,
        collection_name: str,
        token: str,
        api_endpoint: str,
        namespace: Optional[str] = None,
    ) -> Record:
        try:
            import astrapy
        except ImportError:
            raise ImportError(
                "Could not import astrapy package. " "Please install it with `pip install astrapy`."
            )

        memory = AstraDBChatMessageHistory(
            session_id=session_id,
            collection_name=collection_name,
            token=token,
            api_endpoint=api_endpoint,
            namespace=namespace,
        )

        self.add_message(**input_value.data, memory=memory)
        self.status = f"Added message to Astra DB memory for session {session_id}"

        return input_value
