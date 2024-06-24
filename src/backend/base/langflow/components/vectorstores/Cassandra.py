from typing import List

from langchain_community.vectorstores import Cassandra

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers.data import docs_to_data
from langflow.io import (
    DataInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    SecretStrInput,
)
from langflow.schema import Data


class CassandraVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Cassandra"
    description = "Cassandra Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/cassandra"
    icon = "Cassandra"

    inputs = [
        SecretStrInput(
            name="token",
            display_name="Token",
            info="Authentication token for accessing Cassandra on Astra DB.",
            required=True,
        ),
        MessageTextInput(name="database_id", display_name="Database ID", info="The Astra database ID.", required=True),
        MessageTextInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table where vectors will be stored.",
            required=True,
        ),
        MessageTextInput(
            name="keyspace",
            display_name="Keyspace",
            info="Optional key space within Astra DB. The keyspace should already be created.",
            advanced=False,
        ),
        IntInput(
            name="ttl_seconds",
            display_name="TTL Seconds",
            info="Optional time-to-live for the added texts.",
            advanced=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            info="Optional number of data to process in a single batch.",
            value=16,
            advanced=True,
        ),
        MessageTextInput(
            name="body_index_options",
            display_name="Body Index Options",
            info="Optional options used to create the body index.",
            advanced=True,
        ),
        DropdownInput(
            name="setup_mode",
            display_name="Setup Mode",
            info="Configuration mode for setting up the Cassandra table, with options like 'Sync', 'Async', or 'Off'.",
            options=["Sync", "Async", "Off"],
            value="Sync",
            advanced=True,
        ),
        MultilineInput(name="search_query", display_name="Search Query"),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    def build_vector_store(self) -> Cassandra:
        return self._build_cassandra()

    def _build_cassandra(self) -> Cassandra:
        try:
            import cassio
        except ImportError:
            raise ImportError(
                "Could not import cassio integration package. " "Please install it with `pip install cassio`."
            )

        cassio.init(
            database_id=self.database_id,
            token=self.token,
        )

        documents = []

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            table = Cassandra.from_documents(
                documents=documents,
                embedding=self.embedding,
                table_name=self.table_name,
                keyspace=self.keyspace,
                ttl_seconds=self.ttl_seconds,
                batch_size=self.batch_size,
                body_index_options=self.body_index_options,
            )

        else:
            table = Cassandra(
                embedding=self.embedding,
                table_name=self.table_name,
                keyspace=self.keyspace,
                ttl_seconds=self.ttl_seconds,
                body_index_options=self.body_index_options,
                setup_mode=self.setup_mode,
            )

        return table

    def search_documents(self) -> List[Data]:
        vector_store = self._build_cassandra()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            try:
                docs = vector_store.similarity_search(
                    query=self.search_query,
                    k=self.number_of_results,
                )
            except KeyError as e:
                if "content" in str(e):
                    raise ValueError(
                        "You should ingest data through Langflow (or LangChain) to query it in Langflow. Your collection does not contain a field name 'content'."
                    )
                else:
                    raise e

            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []
