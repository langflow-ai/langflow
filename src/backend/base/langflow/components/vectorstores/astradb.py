import os
from collections import defaultdict
from dataclasses import dataclass, field

from astrapy import AstraDBAdmin, DataAPIClient, Database
from langchain_astradb import AstraDBVectorStore, CollectionVectorServiceOptions

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers import docs_to_data
from langflow.inputs import FloatInput, NestedDictInput
from langflow.io import (
    BoolInput,
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

    @dataclass
    class NewDatabaseInput:
        functionality: str = "create"
        fields: dict[str, dict] = field(
            default_factory=lambda: {
                "data": {
                    "node": {
                        "description": "Create a new database in Astra DB.",
                        "display_name": "Create New Database",
                        "field_order": ["new_database_name", "cloud_provider", "region"],
                        "template": {
                            "new_database_name": StrInput(
                                name="new_database_name",
                                display_name="New Database Name",
                                info="Name of the new database to create in Astra DB.",
                                required=True,
                            ),
                            "cloud_provider": DropdownInput(
                                name="cloud_provider",
                                display_name="Cloud Provider",
                                info="Cloud provider for the new database.",
                                options=["Amazon Web Services", "Google Cloud Platform", "Microsoft Azure"],
                                required=True,
                            ),
                            "region": DropdownInput(
                                name="region",
                                display_name="Region",
                                info="Region for the new database.",
                                options=[],
                                required=True,
                            ),
                        },
                    },
                }
            }
        )

    @dataclass
    class NewCollectionInput:
        functionality: str = "create"
        fields: dict[str, dict] = field(
            default_factory=lambda: {
                "data": {
                    "node": {
                        "description": "Create a new collection in Astra DB.",
                        "display_name": "Create New Collection",
                        "field_order": [
                            "new_collection_name",
                            "embedding_generation_provider",
                            "embedding_generation_model",
                        ],
                        "template": {
                            "new_collection_name": StrInput(
                                name="new_collection_name",
                                display_name="New Collection Name",
                                info="Name of the new collection to create in Astra DB.",
                                required=True,
                            ),
                            "embedding_generation_provider": DropdownInput(
                                name="embedding_generation_provider",
                                display_name="Embedding Generation Provider",
                                info="Provider to use for generating embeddings.",
                                options=[],
                                required=True,
                            ),
                            "embedding_generation_model": DropdownInput(
                                name="embedding_generation_model",
                                display_name="Embedding Generation Model",
                                info="Model to use for generating embeddings.",
                                options=[],
                                required=True,
                            ),
                        },
                    },
                }
            }
        )

    inputs = [
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
            real_time_refresh=True,
            input_types=[],
        ),
        StrInput(
            name="environment",
            display_name="Environment",
            info="The environment for the Astra DB API Endpoint.",
            advanced=True,
        ),
        DropdownInput(
            name="api_endpoint",
            display_name="Database",
            info="The Database / API Endpoint for the Astra DB instance.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
        ),
        DropdownInput(
            name="collection_name",
            display_name="Collection",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            # dialog_inputs=asdict(NewCollectionInput()),
            combobox=True,
        ),
        StrInput(
            name="keyspace",
            display_name="Keyspace",
            info="Optional keyspace within Astra DB to use for the collection.",
            advanced=True,
        ),
        DropdownInput(
            name="embedding_choice",
            display_name="Embedding Model or Astra Vectorize",
            info="Choose an embedding model or use Astra Vectorize.",
            options=["Embedding Model", "Astra Vectorize"],
            value="Embedding Model",
            advanced=True,
            real_time_refresh=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            info="Specify the Embedding Model. Not required for Astra Vectorize collections.",
            required=False,
        ),
        *LCVectorStoreComponent.inputs,
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
    ]

    @classmethod
    def map_cloud_providers(cls):
        return {
            "Amazon Web Services": {
                "id": "aws",
                "regions": ["us-east-2", "ap-south-1", "eu-west-1"],
            },
            "Google Cloud Platform": {
                "id": "gcp",
                "regions": ["us-east1"],
            },
            "Microsoft Azure": {
                "id": "azure",
                "regions": ["westus3"],
            },
        }

    @classmethod
    def create_database_api(
        cls,
        token: str,
        new_database_name: str,
        cloud_provider: str,
        region: str,
    ):
        client = DataAPIClient(token=token)

        # Get the admin object
        admin_client = client.get_admin(token=token)

        # Call the create database function
        return admin_client.create_database(
            name=new_database_name,
            cloud_provider=cloud_provider,
            region=region,
        )

    @classmethod
    def create_collection_api(
        cls,
        token: str,
        database_name: str,
        new_collection_name: str,
        dimension: int | None = None,
        embedding_generation_provider: str | None = None,
        embedding_generation_model: str | None = None,
    ):
        client = DataAPIClient(token=token)
        api_endpoint = cls.get_api_endpoint_static(token=token, database_name=database_name)

        # Get the database object
        database = client.get_database(api_endpoint=api_endpoint, token=token)

        # Build vectorize options, if needed
        vectorize_options = None
        if not dimension:
            vectorize_options = CollectionVectorServiceOptions(
                provider=embedding_generation_provider,
                model_name=embedding_generation_model,
                authentication=None,
                parameters=None,
            )

        # Create the collection
        return database.create_collection(
            name=new_collection_name,
            dimension=dimension,
            service=vectorize_options,
        )

    @classmethod
    def get_database_list_static(cls, token: str, environment: str | None = None):
        client = DataAPIClient(token=token, environment=environment)

        # Get the admin object
        admin_client = client.get_admin(token=token)

        # Get the list of databases
        db_list = list(admin_client.list_databases())

        # Generate the api endpoint for each database
        db_info_dict = {}
        for db in db_list:
            try:
                api_endpoint = f"https://{db.info.id}-{db.info.region}.apps.astra.datastax.com"
                db_info_dict[db.info.name] = {
                    "api_endpoint": api_endpoint,
                    "collections": len(
                        list(
                            client.get_database(
                                api_endpoint=api_endpoint, token=token, keyspace=db.info.keyspace
                            ).list_collection_names(keyspace=db.info.keyspace)
                        )
                    ),
                }
            except Exception:  # noqa: BLE001, S110
                pass

        return db_info_dict

    def get_database_list(self):
        return self.get_database_list_static(token=self.token, environment=self.environment)

    @classmethod
    def get_api_endpoint_static(
        cls,
        token: str,
        environment: str | None = None,
        database_name: str | None = None,
    ):
        # Check if the database_name is like a url
        if database_name and database_name.startswith("https://"):
            return database_name

        # If the database is not set, nothing we can do.
        if not database_name:
            return None

        # Otherwise, get the URL from the database list
        return cls.get_database_list_static(token=token, environment=environment).get(database_name).get("api_endpoint")

    def get_api_endpoint(self):
        return self.get_api_endpoint_static(
            token=self.token,
            environment=self.environment,
            database_name=self.api_endpoint,
        )

    def get_keyspace(self):
        keyspace = self.keyspace

        if keyspace:
            return keyspace.strip()

        return None

    def get_database_object(self):
        try:
            client = DataAPIClient(token=self.token, environment=self.environment)

            return client.get_database(
                api_endpoint=self.get_api_endpoint(),
                token=self.token,
                keyspace=self.get_keyspace(),
            )
        except Exception as e:  # noqa: BLE001
            self.log(f"Error getting database: {e}")

            return None

    def collection_exists(self):
        try:
            client = DataAPIClient(token=self.token, environment=self.environment)
            database = client.get_database(
                api_endpoint=self.get_api_endpoint(),
                token=self.token,
                keyspace=self.get_keyspace(),
            )

            return self.collection_name in list(database.list_collection_names(keyspace=self.get_keyspace()))
        except Exception as e:  # noqa: BLE001
            self.log(f"Error getting collection status: {e}")

            return False

    def collection_data(self, collection_name: str, database: Database | None = None):
        try:
            if not database:
                client = DataAPIClient(token=self.token, environment=self.environment)

                database = client.get_database(
                    api_endpoint=self.get_api_endpoint(),
                    token=self.token,
                    keyspace=self.get_keyspace(),
                )

            collection = database.get_collection(collection_name, keyspace=self.get_keyspace())

            return collection.estimated_document_count()
        except Exception as e:  # noqa: BLE001
            self.log(f"Error checking collection data: {e}")

            return None

    def get_vectorize_providers(self):
        try:
            self.log("Dynamically updating list of Vectorize providers.")

            # Get the admin object
            admin = AstraDBAdmin(token=self.token)
            db_admin = admin.get_database_admin(api_endpoint=self.get_api_endpoint())

            # Get the list of embedding providers
            embedding_providers = db_admin.find_embedding_providers().as_dict()

            vectorize_providers_mapping = {}
            # Map the provider display name to the provider key and models
            for provider_key, provider_data in embedding_providers["embeddingProviders"].items():
                display_name = provider_data["displayName"]
                models = [model["name"] for model in provider_data["models"]]

                # TODO: https://astra.datastax.com/api/v2/graphql
                vectorize_providers_mapping[display_name] = [provider_key, models]

            # Sort the resulting dictionary
            return defaultdict(list, dict(sorted(vectorize_providers_mapping.items())))
        except Exception as e:  # noqa: BLE001
            self.log(f"Error fetching Vectorize providers: {e}")

            return {}

    def _initialize_database_options(self):
        try:
            # Directly transform and return the list
            database_list = self.get_database_list()
            return [{"name": name, "collections": info["collections"]} for name, info in database_list.items()]
        except Exception as e:
            self.log(f"Error fetching databases: {e}")
            return []

    def _initialize_collection_options(self):
        database = self.get_database_object()
        if not database:
            return []

        try:
            collection_list = database.list_collections(keyspace=self.get_keyspace())

            # Build list of collections while checking options once
            return [
                {
                    "name": col.name,
                    "records": self.collection_data(collection_name=col.name, database=database),
                    "provider": col.options.vector.service.provider
                    if (col.options.vector and col.options.vector.service)
                    else None,
                    "icon": "",
                    "model": col.options.vector.service.model_name
                    if (col.options.vector and col.options.vector.service)
                    else None,
                }
                for col in collection_list
            ]
        except Exception as e:
            self.log(f"Error fetching collections: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        is_hosted = os.getenv("LANGFLOW_HOST") is not None
        api_endpoint = build_config["api_endpoint"]
        collection_name = build_config["collection_name"]

        # Check and update database options
        if not is_hosted and (
            field_name in ["token", "environment"] or (not api_endpoint.get("options") and not api_endpoint["value"])
        ):
            database_options = self._initialize_database_options()
            collection_name.update({"options": [], "options_metadata": [], "value": ""})

            if database_options:
                api_endpoint.update(
                    {
                        "name": "Database",
                        "display_name": "Database",
                        "options": [db["name"] for db in database_options],
                        "options_metadata": [{k: v for k, v in db.items() if k != "name"} for db in database_options],
                    }
                )
            else:
                api_endpoint.update(
                    {
                        "value": "",
                        "name": "API Endpoint",
                        "display_name": "Astra DB API Endpoint",
                    }
                )
                api_endpoint.pop("options", None)  # Remove options if they exist

        # Update collection name options based on the selected database
        if field_name == "api_endpoint":
            collection_name["value"] = ""
            collection_options = self._initialize_collection_options()
            collection_name["options"] = [col["name"] for col in collection_options]
            collection_name["options_metadata"] = [
                {k: v for k, v in col.items() if k != "name"} for col in collection_options
            ]

        # Adjust embedding model option based on the selected collection
        if field_name == "collection_name" and field_value:
            if not is_hosted and field_value not in collection_name["options"]:
                collection_name["options"].append(field_value)
                collection_name["options_metadata"].append({"records": 0, "provider": None, "icon": "", "model": None})

            index_of_name = collection_name["options"].index(field_value)
            value_of_provider = collection_name["options_metadata"][index_of_name]["provider"]

            embedding_model = build_config["embedding_model"]
            embedding_choice = build_config["embedding_choice"]

            if value_of_provider:
                embedding_model["advanced"] = True
                embedding_choice["value"] = "Astra Vectorize"
            else:
                embedding_model["advanced"] = False
                embedding_choice["value"] = "Embedding Model"

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
        embedding_params = (
            {"embedding": self.embedding_model}
            if self.embedding_model and self.embedding_choice == "Embedding Model"
            else {}
        )

        additional_params = self.astradb_vectorstore_kwargs or {}

        # Get Langflow version and platform information
        __version__ = get_version_info()["version"]
        langflow_prefix = ""
        if os.getenv("LANGFLOW_HOST") is not None:
            langflow_prefix = "ds-"

        # Bundle up the auto-detect parameters
        autodetect_params = {
            "autodetect_collection": self.collection_exists(),  # TODO: May want to expose this option
            "content_field": (
                self.content_field
                if self.content_field and embedding_params
                else (
                    "page_content"
                    if embedding_params and self.collection_data(collection_name=self.collection_name) == 0
                    else None
                )
            ),
            "ignore_invalid_documents": self.ignore_invalid_documents,
        }

        # Attempt to build the Vector Store object
        try:
            vector_store = AstraDBVectorStore(
                # Astra DB Authentication Parameters
                token=self.token,
                api_endpoint=self.get_api_endpoint(),
                namespace=self.get_keyspace(),
                collection_name=self.collection_name,
                environment=self.environment,
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

        if documents and self.deletion_field:
            self.log(f"Deleting documents where {self.deletion_field}")
            try:
                database = self.get_database_object()
                collection = database.get_collection(self.collection_name, keyspace=self.get_keyspace())
                delete_values = list({doc.metadata[self.deletion_field] for doc in documents})
                self.log(f"Deleting documents where {self.deletion_field} matches {delete_values}.")
                collection.delete_many({f"metadata.{self.deletion_field}": {"$in": delete_values}})
            except Exception as e:
                msg = f"Error deleting documents from AstraDBVectorStore based on '{self.deletion_field}': {e}"
                raise ValueError(msg) from e

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
        search_type_mapping = {
            "Similarity with score threshold": "similarity_score_threshold",
            "MMR (Max Marginal Relevance)": "mmr",
        }

        return search_type_mapping.get(self.search_type, "similarity")

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
