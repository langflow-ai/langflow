from langchain_community.vectorstores import Cassandra

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.inputs.inputs import BoolInput, DictInput, FloatInput
from langflow.io import (
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)
from langflow.schema.data import Data


class CassandraVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Cassandra"
    description = "Cassandra Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/cassandra"
    name = "Cassandra"
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
        DropdownInput(
            name="setup_mode",
            display_name="Setup Mode",
            info="Configuration mode for setting up the Cassandra table, with options like 'Sync', 'Async', or 'Off'.",
            options=["Sync", "Async", "Off"],
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
            options=["Similarity", "Similarity with score threshold", "MMR (Max Marginal Relevance)"],
            value="Similarity",
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
        MessageTextInput(
            name="body_search",
            display_name="Search Body",
            info="Document textual search terms to apply to the search query.",
            advanced=True,
        ),
        BoolInput(
            name="enable_body_search",
            display_name="Enable Body Search",
            info="Flag to enable body search. This must be enabled BEFORE the table is created.",
            value=False,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Cassandra:
        try:
            import cassio
            from langchain_community.utilities.cassandra import SetupMode
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

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        body_index_options = [("index_analyzer", "STANDARD")] if self.enable_body_search else None

        if self.setup_mode == "Off":
            setup_mode = SetupMode.OFF
        elif self.setup_mode == "Sync":
            setup_mode = SetupMode.SYNC
        else:
            setup_mode = SetupMode.ASYNC

        if documents:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            table = Cassandra.from_documents(
                documents=documents,
                embedding=self.embedding,
                table_name=self.table_name,
                keyspace=self.keyspace,
                ttl_seconds=self.ttl_seconds or None,
                batch_size=self.batch_size,
                body_index_options=body_index_options,
            )
        else:
            self.log("No documents to add to the Vector Store.")
            table = Cassandra(
                embedding=self.embedding,
                table_name=self.table_name,
                keyspace=self.keyspace,
                ttl_seconds=self.ttl_seconds or None,
                body_index_options=body_index_options,
                setup_mode=setup_mode,
            )
        return table

    def _map_search_type(self) -> str:
        if self.search_type == "Similarity with score threshold":
            return "similarity_score_threshold"
        if self.search_type == "MMR (Max Marginal Relevance)":
            return "mmr"
        return "similarity"

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        self.log(f"Search input: {self.search_query}")
        self.log(f"Search type: {self.search_type}")
        self.log(f"Number of results: {self.number_of_results}")

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            try:
                search_type = self._map_search_type()
                search_args = self._build_search_args()

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

    def _build_search_args(self):
        args = {
            "k": self.number_of_results,
            "score_threshold": self.search_score_threshold,
        }

        if self.search_filter:
            clean_filter = {k: v for k, v in self.search_filter.items() if k and v}
            if len(clean_filter) > 0:
                args["filter"] = clean_filter
        if self.body_search:
            if not self.enable_body_search:
                msg = "You should enable body search when creating the table to search the body field."
                raise ValueError(msg)
            args["body_search"] = self.body_search
        return args

    def get_retriever_kwargs(self):
        search_args = self._build_search_args()
        return {
            "search_type": self._map_search_type(),
            "search_kwargs": search_args,
        }
