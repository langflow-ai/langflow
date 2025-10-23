from astrapy import DataAPIClient
from langchain_core.documents import Document

from lfx.base.datastax.astradb_base import AstraDBBaseComponent
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.vector_store_connection_decorator import vector_store_connection
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DropdownInput, FloatInput, HandleInput, IntInput, NestedDictInput, QueryInput, StrInput
from lfx.schema.data import Data
from lfx.serialization import serialize
from lfx.utils.version import get_version_info


@vector_store_connection
class AstraDBVectorStoreComponent(AstraDBBaseComponent, LCVectorStoreComponent):
    display_name: str = "Astra DB"
    description: str = "Ingest and search documents in Astra DB"
    documentation: str = "https://docs.langflow.org/bundles-datastax#astra-db"
    name = "AstraDB"
    icon: str = "AstraDB"

    inputs = [
        *AstraDBBaseComponent.inputs,
        *LCVectorStoreComponent.inputs,
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            info="Specify the Embedding Model. Not required for Astra Vectorize collections.",
            required=False,
            show=True,
        ),
        StrInput(
            name="content_field",
            display_name="Content Field",
            info="Field to use as the text content field for the vector store.",
            advanced=True,
        ),
        StrInput(
            name="deletion_field",
            display_name="Deletion Based On Field",
            info="When this parameter is provided, documents in the target collection with "
            "metadata field values matching the input metadata field value will be deleted "
            "before new data is loaded.",
            advanced=True,
        ),
        BoolInput(
            name="ignore_invalid_documents",
            display_name="Ignore Invalid Documents",
            info="Boolean flag to determine whether to ignore invalid documents at runtime.",
            advanced=True,
        ),
        NestedDictInput(
            name="astradb_vectorstore_kwargs",
            display_name="AstraDBVectorStore Parameters",
            info="Optional dictionary of additional parameters for the AstraDBVectorStore.",
            advanced=True,
        ),
        DropdownInput(
            name="search_method",
            display_name="Search Method",
            info=(
                "Determine how your content is matched: Vector finds semantic similarity, "
                "and Hybrid Search (suggested) combines both approaches "
                "with a reranker."
            ),
            options=["Hybrid Search", "Vector Search"],  # TODO: Restore Lexical Search?
            options_metadata=[{"icon": "SearchHybrid"}, {"icon": "SearchVector"}],
            value="Vector Search",
            advanced=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="reranker",
            display_name="Reranker",
            info="Post-retrieval model that re-scores results for optimal relevance ranking.",
            show=False,
            toggle=True,
        ),
        QueryInput(
            name="lexical_terms",
            display_name="Lexical Terms",
            info="Add additional terms/keywords to augment search precision.",
            placeholder="Enter terms to search...",
            separator=" ",
            show=False,
            value="",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Search Results",
            info="Number of search results to return.",
            advanced=True,
            value=4,
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
        NestedDictInput(
            name="advanced_search_filter",
            display_name="Search Metadata Filter",
            info="Optional dictionary of filters to apply to the search query.",
            advanced=True,
        ),
    ]

    async def update_build_config(
        self,
        build_config: dict,
        field_value: str | dict,
        field_name: str | None = None,
    ) -> dict:
        """Update build configuration with proper handling of embedding and search options."""
        # Handle base astra db build config updates
        build_config = await super().update_build_config(
            build_config,
            field_value=field_value,
            field_name=field_name,
        )

        # Set embedding model display based on provider selection
        if isinstance(field_value, dict) and "02_embedding_generation_provider" in field_value:
            embedding_provider = field_value.get("02_embedding_generation_provider")
            is_custom_provider = embedding_provider and embedding_provider != "Bring your own"
            provider = embedding_provider.lower() if is_custom_provider and embedding_provider is not None else None

            build_config["embedding_model"]["show"] = not bool(provider)
            build_config["embedding_model"]["required"] = not bool(provider)

        # Early return if no API endpoint is configured
        if not self.get_api_endpoint():
            return build_config

        # Configure search method and related options
        return self._configure_search_options(build_config)

    def _configure_search_options(self, build_config: dict) -> dict:
        """Configure hybrid search, reranker, and vector search options."""
        # Detect available hybrid search capabilities
        hybrid_capabilities = self._detect_hybrid_capabilities()

        # Return if we haven't selected a collection
        if not build_config["collection_name"]["options"] or not build_config["collection_name"]["value"]:
            return build_config

        # Get collection options
        collection_options = self._get_collection_options(build_config)

        # Get the selected collection index
        index = build_config["collection_name"]["options"].index(build_config["collection_name"]["value"])
        provider = build_config["collection_name"]["options_metadata"][index]["provider"]
        build_config["embedding_model"]["show"] = not bool(provider)
        build_config["embedding_model"]["required"] = not bool(provider)

        # Determine search configuration
        is_vector_search = build_config["search_method"]["value"] == "Vector Search"
        is_autodetect = build_config["autodetect_collection"]["value"]

        # Apply hybrid search configuration
        if hybrid_capabilities["available"]:
            build_config["search_method"]["show"] = True
            build_config["search_method"]["options"] = ["Hybrid Search", "Vector Search"]
            build_config["search_method"]["value"] = build_config["search_method"].get("value", "Hybrid Search")

            build_config["reranker"]["options"] = hybrid_capabilities["reranker_models"]
            build_config["reranker"]["options_metadata"] = hybrid_capabilities["reranker_metadata"]
            if hybrid_capabilities["reranker_models"]:
                build_config["reranker"]["value"] = hybrid_capabilities["reranker_models"][0]
        else:
            build_config["search_method"]["show"] = False
            build_config["search_method"]["options"] = ["Vector Search"]
            build_config["search_method"]["value"] = "Vector Search"
            build_config["reranker"]["options"] = []
            build_config["reranker"]["options_metadata"] = []

        # Configure reranker visibility and state
        hybrid_enabled = (
            collection_options["rerank_enabled"] and build_config["search_method"]["value"] == "Hybrid Search"
        )

        build_config["reranker"]["show"] = hybrid_enabled
        build_config["reranker"]["toggle_value"] = hybrid_enabled
        build_config["reranker"]["toggle_disable"] = is_vector_search

        # Configure lexical terms
        lexical_visible = collection_options["lexical_enabled"] and not is_vector_search
        build_config["lexical_terms"]["show"] = lexical_visible
        build_config["lexical_terms"]["value"] = "" if is_vector_search else build_config["lexical_terms"]["value"]

        # Configure search type and score threshold
        build_config["search_type"]["show"] = is_vector_search
        build_config["search_score_threshold"]["show"] = is_vector_search

        # Force similarity search for hybrid mode or autodetect
        if hybrid_enabled or is_autodetect:
            build_config["search_type"]["value"] = "Similarity"

        return build_config

    def _detect_hybrid_capabilities(self) -> dict:
        """Detect available hybrid search and reranking capabilities."""
        environment = self.get_environment(self.environment)
        client = DataAPIClient(environment=environment)
        admin_client = client.get_admin()
        db_admin = admin_client.get_database_admin(self.get_api_endpoint(), token=self.token)

        try:
            providers = db_admin.find_reranking_providers()
            reranker_models = [
                model.name for provider_data in providers.reranking_providers.values() for model in provider_data.models
            ]
            reranker_metadata = [
                {"icon": self.get_provider_icon(provider_name=model.name.split("/")[0])}
                for provider in providers.reranking_providers.values()
                for model in provider.models
            ]
        except Exception as e:  # noqa: BLE001
            self.log(f"Hybrid search not available: {e}")
            return {
                "available": False,
                "reranker_models": [],
                "reranker_metadata": [],
            }
        else:
            return {
                "available": True,
                "reranker_models": reranker_models,
                "reranker_metadata": reranker_metadata,
            }

    def _get_collection_options(self, build_config: dict) -> dict:
        """Retrieve collection-level search options."""
        database = self.get_database_object(api_endpoint=build_config["api_endpoint"]["value"])
        collection = database.get_collection(
            name=build_config["collection_name"]["value"],
            keyspace=build_config["keyspace"]["value"],
        )

        col_options = collection.options()

        return {
            "rerank_enabled": bool(col_options.rerank and col_options.rerank.enabled),
            "lexical_enabled": bool(col_options.lexical and col_options.lexical.enabled),
        }

    @check_cached_vector_store
    def build_vector_store(self):
        try:
            from langchain_astradb import AstraDBVectorStore
            from langchain_astradb.utils.astradb import HybridSearchMode
        except ImportError as e:
            msg = (
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )
            raise ImportError(msg) from e

        # Get the embedding model and additional params
        embedding_params = {"embedding": self.embedding_model} if self.embedding_model else {}

        # Get the additional parameters
        additional_params = self.astradb_vectorstore_kwargs or {}

        # Get Langflow version and platform information
        __version__ = get_version_info()["version"]
        langflow_prefix = ""
        # if os.getenv("AWS_EXECUTION_ENV") == "AWS_ECS_FARGATE":  # TODO: More precise way of detecting
        #     langflow_prefix = "ds-"

        # Get the database object
        database = self.get_database_object()
        autodetect = self.collection_name in database.list_collection_names() and self.autodetect_collection

        # Bundle up the auto-detect parameters
        autodetect_params = {
            "autodetect_collection": autodetect,
            "content_field": (
                self.content_field
                if self.content_field and embedding_params
                else (
                    "page_content"
                    if embedding_params
                    and self.collection_data(collection_name=self.collection_name, database=database) == 0
                    else None
                )
            ),
            "ignore_invalid_documents": self.ignore_invalid_documents,
        }

        # Choose HybridSearchMode based on the selected param
        hybrid_search_mode = HybridSearchMode.DEFAULT if self.search_method == "Hybrid Search" else HybridSearchMode.OFF

        # Attempt to build the Vector Store object
        try:
            vector_store = AstraDBVectorStore(
                # Astra DB Authentication Parameters
                token=self.token,
                api_endpoint=database.api_endpoint,
                namespace=database.keyspace,
                collection_name=self.collection_name,
                environment=self.environment,
                # Hybrid Search Parameters
                hybrid_search=hybrid_search_mode,
                # Astra DB Usage Tracking Parameters
                ext_callers=[(f"{langflow_prefix}langflow", __version__)],
                # Astra DB Vector Store Parameters
                **autodetect_params,
                **embedding_params,
                **additional_params,
            )
        except ValueError as e:
            msg = f"Error initializing AstraDBVectorStore: {e}"
            raise ValueError(msg) from e

        # Add documents to the vector store
        self._add_documents_to_vector_store(vector_store)

        return vector_store

    def _add_documents_to_vector_store(self, vector_store) -> None:
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        documents = [
            Document(page_content=doc.page_content, metadata=serialize(doc.metadata, to_str=True)) for doc in documents
        ]

        if documents and self.deletion_field:
            self.log(f"Deleting documents where {self.deletion_field}")
            try:
                database = self.get_database_object()
                collection = database.get_collection(self.collection_name, keyspace=database.keyspace)
                delete_values = list({doc.metadata[self.deletion_field] for doc in documents})
                self.log(f"Deleting documents where {self.deletion_field} matches {delete_values}.")
                collection.delete_many({f"metadata.{self.deletion_field}": {"$in": delete_values}})
            except ValueError as e:
                msg = f"Error deleting documents from AstraDBVectorStore based on '{self.deletion_field}': {e}"
                raise ValueError(msg) from e

        if documents:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            try:
                vector_store.add_documents(documents)
            except ValueError as e:
                msg = f"Error adding documents to AstraDBVectorStore: {e}"
                raise ValueError(msg) from e
        else:
            self.log("No documents to add to the Vector Store.")

    def _map_search_type(self) -> str:
        search_type_mapping = {
            "Similarity with score threshold": "similarity_score_threshold",
            "MMR (Max Marginal Relevance)": "mmr",
        }

        return search_type_mapping.get(self.search_type, "similarity")

    def _build_search_args(self):
        # Clean up the search query
        query = self.search_query if isinstance(self.search_query, str) and self.search_query.strip() else None
        lexical_terms = self.lexical_terms or None

        # Check if we have a search query, and if so set the args
        if query:
            args = {
                "query": query,
                "search_type": self._map_search_type(),
                "k": self.number_of_results,
                "score_threshold": self.search_score_threshold,
                "lexical_query": lexical_terms,
            }
        elif self.advanced_search_filter:
            args = {
                "n": self.number_of_results,
            }
        else:
            return {}

        filter_arg = self.advanced_search_filter or {}
        if filter_arg:
            args["filter"] = filter_arg

        return args

    def search_documents(self, vector_store=None) -> list[Data]:
        vector_store = vector_store or self.build_vector_store()

        self.log(f"Search input: {self.search_query}")
        self.log(f"Search type: {self.search_type}")
        self.log(f"Number of results: {self.number_of_results}")
        self.log(f"store.hybrid_search: {vector_store.hybrid_search}")
        self.log(f"Lexical terms: {self.lexical_terms}")
        self.log(f"Reranker: {self.reranker}")

        try:
            search_args = self._build_search_args()
        except ValueError as e:
            msg = f"Error in AstraDBVectorStore._build_search_args: {e}"
            raise ValueError(msg) from e

        if not search_args:
            self.log("No search input or filters provided. Skipping search.")
            return []

        docs = []
        search_method = "search" if "query" in search_args else "metadata_search"

        try:
            self.log(f"Calling vector_store.{search_method} with args: {search_args}")
            docs = getattr(vector_store, search_method)(**search_args)
        except ValueError as e:
            msg = f"Error performing {search_method} in AstraDBVectorStore: {e}"
            raise ValueError(msg) from e

        self.log(f"Retrieved documents: {len(docs)}")

        data = docs_to_data(docs)
        self.log(f"Converted documents to data: {len(data)}")
        self.status = data

        return data

    def get_retriever_kwargs(self):
        search_args = self._build_search_args()

        return {
            "search_type": self._map_search_type(),
            "search_kwargs": search_args,
        }
