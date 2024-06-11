from typing import Optional, cast


from langflow.base.memory.memory import BaseMemoryComponent
from langflow.schema.schema import Record


class AstraDBMessageReaderComponent(BaseMemoryComponent):
    display_name = "Astra DB Message Reader"
    description = "Retrieves stored chat messages from Astra DB."

    def build_config(self):
        return {
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "collection_name": {
                "display_name": "Collection Name",
                "info": "Collection name for Astra DB.",
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
            "namespace": {
                "display_name": "Namespace",
                "info": "Namespace for the Astra DB instance.",
                "input_types": ["Text"],
                "advanced": True,
            },
        }

    def get_messages(self, **kwargs) -> list[Record]:
        """
        Retrieves messages from the AstraDBChatMessageHistory memory.

        Args:
            memory (AstraDBChatMessageHistory): The AstraDBChatMessageHistory instance to retrieve messages from.

        Returns:
            list[Record]: A list of Record objects representing the search results.
        """
        try:
            from langchain_astradb.chat_message_histories import AstraDBChatMessageHistory
        except ImportError:
            raise ImportError(
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )

        memory: AstraDBChatMessageHistory = cast(AstraDBChatMessageHistory, kwargs.get("memory"))
        if not memory:
            raise ValueError("AstraDBChatMessageHistory instance is required.")

        # Get messages from the memory
        messages = memory.messages
        results = [Record.from_lc_message(message) for message in messages]

        return list(results)

    def build(
        self,
        session_id: str,
        collection_name: str,
        token: str,
        api_endpoint: str,
        namespace: Optional[str] = None,
    ) -> list[Record]:
        try:
            from langchain_astradb.chat_message_histories import AstraDBChatMessageHistory
        except ImportError:
            raise ImportError(
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )

        memory = AstraDBChatMessageHistory(
            session_id=session_id,
            collection_name=collection_name,
            token=token,
            api_endpoint=api_endpoint,
            namespace=namespace,
        )

        records = self.get_messages(memory=memory)
        self.status = records

        return records
