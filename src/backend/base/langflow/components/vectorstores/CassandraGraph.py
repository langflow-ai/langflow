from typing import List

from langchain_community.graph_vectorstores import CassandraGraphVectorStore
from loguru import logger
from uuid import UUID

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.inputs import DictInput, FloatInput
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


class CassandraGraphVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Cassandra Graph"
    description = "Cassandra Graph Vector Store"
    documentation = "https://python.langchain.com/v0.2/api_reference/community/graph_vectorstores.html"
    name = "CassandraGraph"
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
        DropdownInput(
            name="setup_mode",
            display_name="Setup Mode",
            info="Configuration mode for setting up the Cassandra table, with options like 'Sync' or 'Off'.",
            options=["Sync", "Off"],
            value="Sync",
            advanced=True,
        ),
        DictInput(
            name="cluster_kwargs",
            display_name="Cluster arguments",
            info="Optional dictionary of additional keyword arguments for the Cassandra cluster.",
            advanced=True,
            is_list=True,
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
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            info="Search type to use",
            options=[
                "Traversal",
                "MMR traversal",
                "Similarity",
                "Similarity with score threshold",
                "MMR (Max Marginal Relevance)",
            ],
            value="Traversal",
            advanced=True,
        ),
        IntInput(
            name="depth",
            display_name="Depth of traversal",
            info="The maximum depth of edges to traverse. (when using 'Traversal' or 'MMR traversal')",
            value=1,
            advanced=True,
        ),
        FloatInput(
            name="search_score_threshold",
            display_name="Search Score Threshold",
            info="Minimum similarity score threshold for search results. (when using 'Similarity with score threshold')",
            value=0,
            advanced=True,
        ),
        DictInput(
            name="search_filter",
            display_name="Search Metadata Filter",
            info="Optional dictionary of filters to apply to the search query.",
            advanced=True,
            is_list=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> CassandraGraphVectorStore:
        try:
            import cassio
            from langchain_community.utilities.cassandra import SetupMode
        except ImportError:
            raise ImportError(
                "Could not import cassio integration package. " "Please install it with `pip install cassio`."
            )

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
        documents = []

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if self.setup_mode == "Off":
            setup_mode = SetupMode.OFF
        else:
            setup_mode = SetupMode.SYNC

        if documents:
            logger.debug(f"Adding {len(documents)} documents to the Vector Store.")
            store = CassandraGraphVectorStore.from_documents(
                documents=documents,
                embedding=self.embedding,
                node_table=self.table_name,
                keyspace=self.keyspace,
            )
        else:
            logger.debug("No documents to add to the Vector Store.")
            store = CassandraGraphVectorStore(
                embedding=self.embedding,
                node_table=self.table_name,
                keyspace=self.keyspace,
                setup_mode=setup_mode,
            )
        return store

    def _map_search_type(self):
        if self.search_type == "Similarity":
            return "similarity"
        elif self.search_type == "Similarity with score threshold":
            return "similarity_score_threshold"
        elif self.search_type == "MMR (Max Marginal Relevance)":
            return "mmr"
        elif self.search_type == "MMR Traversal":
            return "mmr_traversal"
        else:
            return "traversal"

    def search_documents(self) -> List[Data]:
        vector_store = self.build_vector_store()

        logger.debug(f"Search input: {self.search_query}")
        logger.debug(f"Search type: {self.search_type}")
        logger.debug(f"Number of results: {self.number_of_results}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            try:
                search_type = self._map_search_type()
                search_args = self._build_search_args()

                logger.debug(f"Search args: {str(search_args)}")

                docs = vector_store.search(query=self.search_query, search_type=search_type, **search_args)
            except KeyError as e:
                if "content" in str(e):
                    raise ValueError(
                        "You should ingest data through Langflow (or LangChain) to query it in Langflow. Your collection does not contain a field name 'content'."
                    ) from e
                else:
                    raise e

            logger.debug(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []

    def _build_search_args(self):
        args = {
            "k": self.number_of_results,
            "score_threshold": self.search_score_threshold,
            "depth": self.depth,
        }

        if self.search_filter:
            clean_filter = {k: v for k, v in self.search_filter.items() if k and v}
            if len(clean_filter) > 0:
                args["filter"] = clean_filter
        return args

    def get_retriever_kwargs(self):
        search_args = self._build_search_args()
        return {
            "search_type": self._map_search_type(),
            "search_kwargs": search_args,
        }
