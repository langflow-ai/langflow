from typing import Optional

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.schema.schema import Record

from langchain_core.messages import BaseMessage
from langchain_community.chat_message_histories import CassandraChatMessageHistory


class CassandraMessageWriterComponent(BaseMemoryComponent):
    display_name = "Cassandra Message Writer"
    description = "Writes a message to a Cassandra table on Astra DB."

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Input Record",
                "info": "Record to write to Cassandra.",
            },
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "database_id": {
                "display_name": "Database ID",
                "info": "The Astra database ID.",
            },
            "table_name": {
                "display_name": "Table Name",
                "info": "The name of the table where messages will be stored.",
            },
            "token": {
                "display_name": "Token",
                "info": "Authentication token for accessing Cassandra on Astra DB.",
                "password": True,
            },
            "keyspace": {
                "display_name": "Keyspace",
                "info": "Optional key space within Astra DB. The keyspace should already be created.",
                "input_types": ["Text"],
                "advanced": True,
            },
            "ttl_seconds": {
                "display_name": "TTL Seconds",
                "info": "Optional time-to-live for the messages.",
                "input_types": ["Number"],
                "advanced": True,
            },
        }

    def add_message(
        self,
        sender: str,
        sender_name: str,
        text: str,
        session_id: str,
        metadata: Optional[dict] = None,
        **kwargs,
    ):
        """
        Adds a message to the CassandraChatMessageHistory memory.

        Args:
            sender (str): The type of the message sender. Typically "ai" or "human".
            sender_name (str): The name of the message sender.
            text (str): The content of the message.
            session_id (str): The session ID associated with the message.
            metadata (dict | None, optional): Additional metadata for the message. Defaults to None.
            **kwargs: Additional keyword arguments, including:
                memory (CassandraChatMessageHistory | None): The memory instance to add the message to.


        Raises:
            ValueError: If the CassandraChatMessageHistory instance is not provided.

        """
        memory: CassandraChatMessageHistory | None = kwargs.pop("memory", None)
        if memory is None:
            raise ValueError("CassandraChatMessageHistory instance is required.")

        text_list = [
            BaseMessage(
                content=text,
                sender=sender,
                sender_name=sender_name,
                metadata=metadata,
                session_id=session_id,
            )
        ]

        memory.add_messages(text_list)

    def build(
        self,
        input_value: Record,
        session_id: str,
        table_name: str,
        token: str,
        database_id: str,
        keyspace: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Record:
        try:
            import cassio
        except ImportError:
            raise ImportError(
                "Could not import cassio integration package. " "Please install it with `pip install cassio`."
            )

        cassio.init(token=token, database_id=database_id)
        memory = CassandraChatMessageHistory(
            session_id=session_id,
            table_name=table_name,
            keyspace=keyspace,
            ttl_seconds=ttl_seconds,
        )

        self.add_message(**input_value.data, memory=memory)
        self.status = f"Added message to Cassandra memory for session {session_id}"

        return input_value
