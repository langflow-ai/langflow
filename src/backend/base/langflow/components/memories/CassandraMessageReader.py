from typing import Optional, cast

from langchain_community.chat_message_histories import CassandraChatMessageHistory

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.schema.schema import Record


class CassandraMessageReaderComponent(BaseMemoryComponent):
    display_name = "Cassandra Message Reader"
    description = "Retrieves stored chat messages from a Cassandra table on Astra DB."

    def build_config(self):
        return {
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
                "info": "The name of the table where messages are stored.",
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
        }

    def get_messages(self, **kwargs) -> list[Record]:
        """
        Retrieves messages from the CassandraChatMessageHistory memory.

        Args:
            memory (CassandraChatMessageHistory): The CassandraChatMessageHistory instance to retrieve messages from.

        Returns:
            list[Record]: A list of Record objects representing the search results.
        """
        memory: CassandraChatMessageHistory = cast(CassandraChatMessageHistory, kwargs.get("memory"))
        if not memory:
            raise ValueError("CassandraChatMessageHistory instance is required.")

        # Get messages from the memory
        messages = memory.messages
        results = [Record.from_lc_message(message) for message in messages]

        return list(results)

    def build(
        self,
        session_id: str,
        table_name: str,
        token: str,
        database_id: str,
        keyspace: Optional[str] = None,
    ) -> list[Record]:
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
        )

        records = self.get_messages(memory=memory)
        self.status = records

        return records
