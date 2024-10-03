from langflow.base.memory.model import LCChatMemoryComponent
from langflow.field_typing import BaseChatMessageHistory
from langflow.inputs import DictInput, MessageTextInput, SecretStrInput


class CassandraChatMemory(LCChatMemoryComponent):
    display_name = "Cassandra Chat Memory"
    description = "Retrieves and store chat messages from Apache Cassandra."
    name = "CassandraChatMemory"
    icon = "Cassandra"

    inputs = [
        MessageTextInput(
            name="database_ref",
            display_name="Contact Points / Astra Database ID",
            info="Contact points for the database (or AstraDB database ID)",
            required=True,
        ),
        MessageTextInput(
            name="username", display_name="Username", info="Username for the database (leave empty for AstraDB)."
        ),
        SecretStrInput(
            name="token",
            display_name="Password / AstraDB Token",
            info="User password for the database (or AstraDB token).",
            required=True,
        ),
        MessageTextInput(
            name="keyspace",
            display_name="Keyspace",
            info="Table Keyspace (or AstraDB namespace).",
            required=True,
        ),
        MessageTextInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table (or AstraDB collection) where vectors will be stored.",
            required=True,
        ),
        MessageTextInput(
            name="session_id", display_name="Session ID", info="Session ID for the message.", advanced=True
        ),
        DictInput(
            name="cluster_kwargs",
            display_name="Cluster arguments",
            info="Optional dictionary of additional keyword arguments for the Cassandra cluster.",
            advanced=True,
            is_list=True,
        ),
    ]

    def build_message_history(self) -> BaseChatMessageHistory:
        from langchain_community.chat_message_histories import CassandraChatMessageHistory

        try:
            import cassio
        except ImportError as e:
            msg = "Could not import cassio integration package. Please install it with `pip install cassio`."
            raise ImportError(msg) from e

        from uuid import UUID

        database_ref = self.database_ref

        try:
            UUID(self.database_ref)
            is_astra = True
        except ValueError:
            is_astra = False
            if "," in self.database_ref:
                # use a copy because we can't change the type of the parameter
                database_ref = self.database_ref.split(",")

        if is_astra:
            cassio.init(
                database_id=database_ref,
                token=self.token,
                cluster_kwargs=self.cluster_kwargs,
            )
        else:
            cassio.init(
                contact_points=database_ref,
                username=self.username,
                password=self.token,
                cluster_kwargs=self.cluster_kwargs,
            )

        return CassandraChatMessageHistory(
            session_id=self.session_id,
            table_name=self.table_name,
            keyspace=self.keyspace,
        )
