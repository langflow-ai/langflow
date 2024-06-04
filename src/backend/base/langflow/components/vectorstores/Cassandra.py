from typing import Any, List, Optional, Tuple
from langchain_community.vectorstores import Cassandra
from langchain_community.utilities.cassandra import SetupMode

from langflow.custom import CustomComponent
from langflow.field_typing import Embeddings, VectorStore
from langflow.schema import Record


class CassandraVectorStoreComponent(CustomComponent):
    display_name = "Cassandra"
    description = "Builds or loads a Cassandra Vector Store."
    icon = "Cassandra"
    field_order = ["token", "database_id", "table_name", "inputs", "embedding"]

    def build_config(self):
        return {
            "inputs": {
                "display_name": "Inputs",
                "info": "Optional list of records to be processed and stored in the vector store.",
            },
            "embedding": {"display_name": "Embedding", "info": "Embedding to use"},
            "token": {
                "display_name": "Token",
                "info": "Authentication token for accessing Cassandra on Astra DB.",
                "password": True,
            },
            "database_id": {
                "display_name": "Database ID",
                "info": "The Astra database ID.",
            },
            "table_name": {
                "display_name": "Table Name",
                "info": "The name of the table where vectors will be stored.",
            },
            "keyspace": {
                "display_name": "Keyspace",
                "info": "Optional key space within Astra DB. The keyspace should already be created.",
                "advanced": True,
            },
            "ttl_seconds": {
                "display_name": "TTL Seconds",
                "info": "Optional time-to-live for the added texts.",
                "advanced": True,
            },
            "batch_size": {
                "display_name": "Batch Size",
                "info": "Optional number of records to process in a single batch.",
                "advanced": True,
            },
            "body_index_options": {
                "display_name": "Body Index Options",
                "info": "Optional options used to create the body index.",
                "advanced": True,
            },
            "setup_mode": {
                "display_name": "Setup Mode",
                "info": "Configuration mode for setting up the Cassandra table, with options like 'Sync', 'Async', or 'Off'.",
                "options": ["Sync", "Async", "Off"],
                "advanced": True,
            },
        }

    def build(
        self,
        embedding: Embeddings,
        token: str,
        database_id: str,
        inputs: Optional[List[Record]] = None,
        keyspace: Optional[str] = None,
        table_name: str = "",
        ttl_seconds: Optional[int] = None,
        batch_size: int = 16,
        body_index_options: Optional[List[Tuple[str, Any]]] = None,
        setup_mode: SetupMode = SetupMode.SYNC,
    ) -> VectorStore:
        try:
            import cassio
        except ImportError:
            raise ImportError(
                "Could not import cassio integration package. " "Please install it with `pip install cassio`."
            )

        cassio.init(
            database_id=database_id,
            token=token,
        )

        if inputs:
            documents = [_input.to_lc_document() for _input in inputs]
            table = Cassandra.from_documents(
                documents=documents,
                embedding=embedding,
                table_name=table_name,
                keyspace=keyspace,
                ttl_seconds=ttl_seconds,
                batch_size=batch_size,
                body_index_options=body_index_options,
            )
        else:
            table = Cassandra(
                embedding=embedding,
                table_name=table_name,
                keyspace=keyspace,
                ttl_seconds=ttl_seconds,
                body_index_options=body_index_options,
                setup_mode=setup_mode,
            )

        return table
