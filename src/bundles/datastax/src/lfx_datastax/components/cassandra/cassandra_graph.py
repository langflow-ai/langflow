"""Cassandra graph-vector-store component."""

from types import MappingProxyType
from uuid import UUID

from langchain_community.graph_vectorstores import CassandraGraphVectorStore

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.inputs.inputs import DictInput, FloatInput
from lfx.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx_datastax.components.cassandra._ssrf import validate_cassandra_connection

# Labels are stored in saved flows: never rename them.
SEARCH_TYPES = MappingProxyType(
    {
        "Traversal": "traversal",
        "MMR traversal": "mmr_traversal",
        "Similarity": "similarity",
        "Similarity with score threshold": "similarity_score_threshold",
        "MMR (Max Marginal Relevance)": "mmr",
    }
)


class CassandraGraphVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Cassandra Graph"
    description = "Cassandra Graph Vector Store"
    name = "CassandraGraph"
    icon = "Cassandra"

    inputs = [
        MessageTextInput(
            name="database_ref",
            display_name="Contact Points / Astra Database ID",
            info="Contact points for the database (or Astra DB database ID)",
            required=True,
        ),
        MessageTextInput(
            name="username", display_name="Username", info="Username for the database (leave empty for Astra DB)."
        ),
        SecretStrInput(
            name="token",
            display_name="Password / Astra DB Token",
            info="User password for the database (or Astra DB token).",
            required=True,
        ),
        MessageTextInput(
            name="keyspace",
            display_name="Keyspace",
            info="Table Keyspace (or Astra DB namespace).",
            required=True,
        ),
        MessageTextInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table (or Astra DB collection) where vectors will be stored.",
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
            list=True,
        ),
        *LCVectorStoreComponent.inputs,
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
            options=list(SEARCH_TYPES),
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
            info="Minimum similarity score threshold for search results. "
            "(when using 'Similarity with score threshold')",
            value=0,
            advanced=True,
        ),
        DictInput(
            name="search_filter",
            display_name="Search Metadata Filter",
            info="Optional dictionary of filters to apply to the search query.",
            advanced=True,
            list=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> CassandraGraphVectorStore:
        try:
            import cassio
            from langchain_community.utilities.cassandra import SetupMode
        except ImportError as e:
            msg = "Could not import cassio integration package. Please install it with `pip install cassio`."
            raise ImportError(msg) from e

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
            cluster_kwargs = validate_cassandra_connection(database_ref, self.cluster_kwargs)
            cassio.init(
                contact_points=database_ref,
                username=self.username,
                password=self.token,
                cluster_kwargs=cluster_kwargs,
            )

        self.ingest_data = self._prepare_ingest_data()

        documents = []

        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        setup_mode = SetupMode.OFF if self.setup_mode == "Off" else SetupMode.SYNC

        if documents:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            store = CassandraGraphVectorStore.from_documents(
                documents=documents,
                embedding=self.embedding,
                table_name=self.table_name,
                keyspace=self.keyspace,
            )
        else:
            self.log("No documents to add to the Vector Store.")
            store = CassandraGraphVectorStore(
                embedding=self.embedding,
                table_name=self.table_name,
                keyspace=self.keyspace,
                setup_mode=setup_mode,
            )
        return store

    def _map_search_type(self) -> str:
        search_type = SEARCH_TYPES.get(self.search_type)
        if search_type is None:
            logger.warning(f"Unknown Cassandra Graph search type {self.search_type!r}; falling back to 'traversal'.")
            return "traversal"
        return search_type

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        self.log(f"Search input: {self.search_query}")
        self.log(f"Search type: {self.search_type}")
        self.log(f"Number of results: {self.number_of_results}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            search_type = self._map_search_type()
            if search_type == "similarity_score_threshold":
                # CassandraGraphVectorStore has no relevance score function; langchain raises a bare
                # NotImplementedError that the UI shows as an unknown error.
                msg = (
                    "Cassandra Graph doesn't support 'Similarity with score threshold'. "
                    "Use 'Similarity' or 'MMR traversal'."
                )
                raise ValueError(msg)
            try:
                search_args = self._build_search_args(search_type)

                self.log(f"Search args: {search_args}")

                docs = vector_store.search(query=self.search_query, search_type=search_type, **search_args)
            except KeyError as e:
                if "content" in str(e):
                    msg = (
                        "You should ingest data through Langflow (or LangChain) to query it in Langflow. "
                        "Your collection does not contain a field name 'content'."
                    )
                    raise ValueError(msg) from e
                raise

            self.log(f"Retrieved documents: {len(docs)}")

            data = docs_to_data(docs)
            self.status = data
            return data
        return []

    def _build_search_args(self, search_type: str) -> dict:
        args = {
            "k": self.number_of_results,
            # mmr_traversal starts its candidates at depth 0 and only follows edges while
            # depth + 1 < limit, so it needs one more than traversal for the same hop count.
            "depth": self.depth + 1 if search_type == "mmr_traversal" else self.depth,
        }
        # mmr_traversal also uses score_threshold as an MMR-score cutoff, so a default of 0
        # silently drops results; the input only promises it for this search type.
        if search_type == "similarity_score_threshold":
            args["score_threshold"] = self.search_score_threshold

        if self.search_filter:
            clean_filter = {k: v for k, v in self.search_filter.items() if k and v}
            if len(clean_filter) > 0:
                args["filter"] = clean_filter
        return args

    def get_retriever_kwargs(self):
        search_type = self._map_search_type()
        return {
            "search_type": search_type,
            "search_kwargs": self._build_search_args(search_type),
        }
