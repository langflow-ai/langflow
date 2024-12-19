import os

from astrapy import DataAPIClient
from astrapy.admin import parse_api_endpoint
from langchain_astradb import AstraDBVectorStore

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers import docs_to_data
from langflow.inputs import DictInput, FloatInput, MessageTextInput, NestedDictInput
from langflow.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data
from langflow.utils.version import get_version_info


class AstraDBVectorStoreComponent(LCVectorStoreComponent):
    display_name: str = "Astra DB"
    description: str = "Ingest and search documents in Astra DB"
    documentation: str = "https://docs.datastax.com/en/langflow/astra-components.html"
    name = "AstraDB"
    icon: str = "AstraDB"

    _cached_vector_store: AstraDBVectorStore | None = None

    class NewDatabaseInput(DictInput):
        title: str = "Create New Database"
        description: str = "Create a new database in Astra DB."
        db_names: list[str] = []
        status: str = ""
        collection_count: int = 0
        record_count: int = 0

    class NewCollectionInput(DictInput):
        title: str = "Create New Collection"
        description: str = "Create a new collection in Astra DB."
        status: str = ""
        dimensions: int = 0
        model: str = ""
        similarity_metrics: list[str] = []
        icon: str = "Collection"

    base_inputs = LCVectorStoreComponent.inputs
    if "search_query" not in [input_.name for input_ in base_inputs]:
        base_inputs.append(
            MessageTextInput(
                name="search_query",
                display_name="Search Query",
                tool_mode=True,
            )
        )
    if "ingest_data" not in [input_.name for input_ in base_inputs]:
        base_inputs.append(
            DataInput(
                name="ingest_data",
                display_name="Ingest Data",
            )
        )

    inputs = [
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
            advanced=os.getenv("ASTRA_ENHANCED", "false").lower() == "true",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_endpoint",
            display_name="API Endpoint",
            info="The Astra DB API Endpoint to use. Overrides selection of database.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            advanced=True,
        ),
        DropdownInput(
            name="database_name",
            display_name="Database",
            info="Select a database in Astra DB.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            dialog_inputs=[NewDatabaseInput(name="database_input").__dict__],
            options=[],
            value="",
        ),
        DropdownInput(
            name="collection_name",
            display_name="Collection",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            dialog_inputs=[NewCollectionInput(name="collection_input").__dict__],
            options=[],
            value="",
        ),
        StrInput(
            name="keyspace",
            display_name="Keyspace",
            info="Optional keyspace within Astra DB to use for the collection.",
            advanced=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            info="Allows an embedding model configuration.",
        ),
        *base_inputs,
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
        StrInput(
            name="content_field",
            display_name="Content Field",
            info="Field to use as the text content field for the vector store.",
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
    ]

    def get_database_list(self):
        # Get the admin object
        client = DataAPIClient(token=self.token)
        admin_client = client.get_admin(token=self.token)
        db_list = list(admin_client.list_databases())

        # Generate the api endpoint for each database
        return {
            db.info.name: {
                "api_endpoint": f"https://{db.info.id}-{db.info.region}.apps.astra.datastax.com",
                "collections": len(list(client.get_database(db.info.id, token=self.token).list_collection_names())),
                "records": 0,
            }
            for db in db_list
        }

    def get_api_endpoint(self):
        # If the API endpoint is set, return it
        if self.api_endpoint:
            return self.api_endpoint

        # If the database is not set, nothing we can do.
        if not self.database_name:
            return None

        # Otherwise, get the URL from the database list
        return self.get_database_list().get(self.database_name)

    def get_database(self):
        try:
            client = DataAPIClient(token=self.token)

            return client.get_database(
                self.get_api_endpoint(),
                token=self.token,
            )
        except Exception as e:  # noqa: BLE001
            self.log(f"Error getting database: {e}")

            return None

    def collection_exists(self):
        try:
            client = DataAPIClient(token=self.token)
            database = client.get_database(
                self.get_api_endpoint(),
                token=self.token,
            )
            return self.collection_name in list(database.list_collections())
        except Exception as e:  # noqa: BLE001
            self.log(f"Error getting collection status: {e}")

            return False

    def _initialize_database_options(self):
        try:
            return [
                {"name": name, "collections": info["collections"], "records": info["records"]}
                for name, info in self.get_database_list().items()
            ]
        except Exception as e:  # noqa: BLE001
            self.log(f"Error fetching databases: {e}")

            return []

    def _initialize_collection_options(self):
        database = self.get_database()
        if database is None:
            return []

        try:
            collection_list = list(database.list_collections())

            return [
                {
                    "name": col.name,
                    "records": 0,
                    "provider": col.options.vector.service.provider if col.options.vector else "",
                    "model": col.options.vector.service.model_name if col.options.vector else "",
                }
                for col in collection_list
            ]
        except Exception as e:  # noqa: BLE001
            self.log(f"Error fetching collections: {e}")

            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):  # noqa: ARG002
        # Refresh the collection name options
        build_config["database_name"]["options"] = self._initialize_database_options()
        build_config["collection_name"]["options"] = self._initialize_collection_options()

        return build_config

    @check_cached_vector_store
    def build_vector_store(self):
        try:
            from langchain_astradb import AstraDBVectorStore
        except ImportError as e:
            msg = (
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )
            raise ImportError(msg) from e

        # Get the embedding model and additional params
        embedding_params = {"embedding": self.embedding_model} if self.embedding_model else {}
        additional_params = self.astradb_vectorstore_kwargs or {}

        # Get the running environment for Langflow
        environment = (
            parse_api_endpoint(self.get_api_endpoint()).environment if self.get_api_endpoint() is not None else None
        )

        # Get Langflow version and platform information
        __version__ = get_version_info()["version"]
        langflow_prefix = ""
        if os.getenv("LANGFLOW_HOST") is not None:
            langflow_prefix = "ds-"

        # Bundle up the auto-detect parameters
        autodetect_params = {
            "autodetect_collection": self.collection_exists(),  # TODO: May want to expose this option
            "content_field": self.content_field or None,
            "ignore_invalid_documents": self.ignore_invalid_documents,
        }

        # Attempt to build the Vector Store object
        try:
            vector_store = AstraDBVectorStore(
                # Astra DB Authentication Parameters
                token=self.token,
                api_endpoint=self.get_api_endpoint(),
                namespace=self.keyspace or None,
                collection_name=self.collection_name,
                environment=environment,
                # Astra DB Usage Tracking Parameters
                ext_callers=[(f"{langflow_prefix}langflow", __version__)],
                # Astra DB Vector Store Parameters
                **autodetect_params,
                **embedding_params,
                **additional_params,
            )
        except Exception as e:
            msg = f"Error initializing AstraDBVectorStore: {e}"
            raise ValueError(msg) from e

        self._add_documents_to_vector_store(vector_store)

        return vector_store

    def _add_documents_to_vector_store(self, vector_store) -> None:
        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        if documents:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            try:
                vector_store.add_documents(documents)
            except Exception as e:
                msg = f"Error adding documents to AstraDBVectorStore: {e}"
                raise ValueError(msg) from e
        else:
            self.log("No documents to add to the Vector Store.")

    def _map_search_type(self) -> str:
        if self.search_type == "Similarity with score threshold":
            return "similarity_score_threshold"
        if self.search_type == "MMR (Max Marginal Relevance)":
            return "mmr"
        return "similarity"

    def _build_search_args(self):
        query = self.search_query if isinstance(self.search_query, str) and self.search_query.strip() else None

        if query:
            args = {
                "query": query,
                "search_type": self._map_search_type(),
                "k": self.number_of_results,
                "score_threshold": self.search_score_threshold,
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

        try:
            search_args = self._build_search_args()
        except Exception as e:
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
        except Exception as e:
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
