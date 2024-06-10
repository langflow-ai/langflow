from typing import Any, List, Optional, Tuple

from langflow.components.vectorstores.Cassandra import CassandraVectorStoreComponent
from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.field_typing import Embeddings, Text
from langflow.schema import Record
from langchain_community.utilities.cassandra import SetupMode


class CassandraSearchComponent(LCVectorStoreComponent):
    display_name = "Cassandra Search"
    description = "Searches an existing Cassandra Vector Store."
    icon = "Cassandra"
    field_order = ["token", "database_id", "table_name", "input_value", "embedding"]

    def build_config(self):
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {
                "display_name": "Input Value",
                "info": "Input value to search",
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
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(
        self,
        embedding: Embeddings,
        table_name: str,
        input_value: Text,
        token: str,
        database_id: str,
        search_type: str = "similarity",
        number_of_results: int = 4,
        keyspace: Optional[str] = None,
        body_index_options: Optional[List[Tuple[str, Any]]] = None,
        setup_mode: SetupMode = SetupMode.SYNC,
    ) -> List[Record]:
        vector_store = CassandraVectorStoreComponent().build(
            embedding=embedding,
            table_name=table_name,
            token=token,
            database_id=database_id,
            keyspace=keyspace,
            body_index_options=body_index_options,
            setup_mode=setup_mode,
        )

        try:
            return self.search_with_vector_store(input_value, search_type, vector_store, k=number_of_results)
        except KeyError as e:
            if "content" in str(e):
                raise ValueError(
                    "You should ingest data through Langflow (or LangChain) to query it in Langflow. Your collection does not contain a field name 'content'."
                )
            else:
                raise e
