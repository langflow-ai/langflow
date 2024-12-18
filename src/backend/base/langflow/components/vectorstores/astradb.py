import os
from collections import defaultdict

from astrapy import AstraDBAdmin, DataAPIClient
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
        DropdownInput(
            name="api_endpoint",
            display_name="Database",
            info="The Astra DB Database to use.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            options=["Default database"],
            value="Default database",
        ),
        DropdownInput(
            name="collection_name",
            display_name="Collection",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            options=["+ Create new collection"],
            value="+ Create new collection",
        ),
        StrInput(
            name="collection_name_new",
            display_name="Collection Name",
            info="Name of the new collection to create.",
            advanced=os.getenv("LANGFLOW_HOST") is not None,
            required=os.getenv("LANGFLOW_HOST") is None,
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
            info="Determines whether to use Astra Vectorize for the collection.",
            options=["Embedding Model", "Astra Vectorize"],
            real_time_refresh=True,
            value="Embedding Model",
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

    def del_fields(self, build_config, field_list):
        for field in field_list:
            if field in build_config:
                del build_config[field]

        return build_config

    def insert_in_dict(self, build_config, field_name, new_parameters):
        # Insert the new key-value pair after the found key
        for new_field_name, new_parameter in new_parameters.items():
            # Get all the items as a list of tuples (key, value)
            items = list(build_config.items())

            # Find the index of the key to insert after
            idx = len(items)
            for i, (key, _) in enumerate(items):
                if key == field_name:
                    idx = i + 1
                    break

            items.insert(idx, (new_field_name, new_parameter))

            # Clear the original dictionary and update with the modified items
            build_config.clear()
            build_config.update(items)

        return build_config

    def get_vectorize_providers(self):
        try:
            self.log("Dynamically updating list of Vectorize providers.")

            # Get the admin object
            admin = AstraDBAdmin(token=self.token)
            db_admin = admin.get_database_admin(self.get_api_endpoint())

            # Get the list of embedding providers
            embedding_providers = db_admin.find_embedding_providers().as_dict()

            vectorize_providers_mapping = {}
            # Map the provider display name to the provider key and models
            for provider_key, provider_data in embedding_providers["embeddingProviders"].items():
                display_name = provider_data["displayName"]
                models = [model["name"] for model in provider_data["models"]]

                vectorize_providers_mapping[display_name] = [provider_key, models]

            # Sort the resulting dictionary
            return defaultdict(list, dict(sorted(vectorize_providers_mapping.items())))
        except Exception as e:  # noqa: BLE001
            self.log(f"Error fetching Vectorize providers: {e}")

            return {}

    def get_database_list(self):
        # Get the admin object
        db_admin = AstraDBAdmin(token=self.token)
        db_list = list(db_admin.list_databases())

        # Generate the api endpoint for each database
        return {db.info.name: f"https://{db.info.id}-{db.info.region}.apps.astra.datastax.com" for db in db_list}

    def get_api_endpoint(self):
        # Get the database name (or endpoint)
        database = self.api_endpoint

        # If the database is not set, get the first database in the list
        if not database or database == "Default database":
            database, _ = next(iter(self.get_database_list().items()))

        # If the database is a URL, return it
        if database.startswith("https://"):
            return database

        # Otherwise, get the URL from the database list
        return self.get_database_list().get(database)

    def get_database(self):
        try:
            client = DataAPIClient(token=self.token)

            return client.get_database(
                api_endpoint=self.get_api_endpoint(),
                token=self.token,
            )
        except Exception as e:  # noqa: BLE001
            self.log(f"Error getting database: {e}")

            return None

    def _initialize_database_options(self):
        if not self.token:
            return ["Default database"]
        try:
            databases = ["Default database", *list(self.get_database_list().keys())]
        except Exception as e:  # noqa: BLE001
            self.log(f"Error fetching databases: {e}")

            return ["Default database"]

        return databases

    def _initialize_collection_options(self):
        database = self.get_database()
        if database is None:
            return ["+ Create new collection"]

        try:
            collections = [collection.name for collection in database.list_collections(keyspace=self.keyspace or None)]
        except Exception as e:  # noqa: BLE001
            self.log(f"Error fetching collections: {e}")

            return ["+ Create new collection"]

        return [*collections, "+ Create new collection"]

    def get_collection_choice(self):
        collection_name = self.collection_name
        if collection_name == "+ Create new collection":
            return self.collection_name_new

        return collection_name

    def get_collection_options(self):
        # Only get the options if the collection exists
        database = self.get_database()
        if database is None:
            return None

        collection_name = self.get_collection_choice()

        try:
            collection = database.get_collection(collection_name, keyspace=self.keyspace or None)
            collection_options = collection.options()
        except Exception as _:  # noqa: BLE001
            return None

        return collection_options.vector

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        # Always attempt to update the database list
        if field_name in ["token", "api_endpoint", "collection_name"]:
            # Update the database selector
            build_config["api_endpoint"]["options"] = self._initialize_database_options()

            # Set the default API endpoint if not set
            if build_config["api_endpoint"]["value"] == "Default database":
                build_config["api_endpoint"]["value"] = build_config["api_endpoint"]["options"][0]

            # Update the collection selector
            build_config["collection_name"]["options"] = self._initialize_collection_options()

        # Update the choice of embedding model based on collection name
        if field_name == "collection_name":
            # Detect if it is a new collection
            is_new_collection = field_value == "+ Create new collection"

            # Set the advanced and required fields based on the collection choice
            build_config["embedding_choice"].update(
                {
                    "advanced": not is_new_collection,
                    "value": "Embedding Model" if is_new_collection else build_config["embedding_choice"].get("value"),
                }
            )

            # Set the advanced field for the embedding model
            build_config["embedding_model"]["advanced"] = not is_new_collection

            # Set the advanced and required fields for the new collection name
            build_config["collection_name_new"].update(
                {
                    "advanced": not is_new_collection,
                    "required": is_new_collection,
                    "value": "" if not is_new_collection else build_config["collection_name_new"].get("value"),
                }
            )

        # Get the collection options for the selected collection
        collection_options = self.get_collection_options()

        # If the collection options are available (DB exists), show the advanced options
        if collection_options:
            build_config["embedding_choice"]["advanced"] = True

            if collection_options.service:
                # Remove unnecessary fields when a service is set
                self.del_fields(
                    build_config,
                    [
                        "embedding_provider",
                        "model",
                        "z_01_model_parameters",
                        "z_02_api_key_name",
                        "z_03_provider_api_key",
                        "z_04_authentication",
                    ],
                )

                # Update the providers mapping
                updates = {
                    "embedding_model": {"advanced": True},
                    "embedding_choice": {"value": "Astra Vectorize"},
                }
            else:
                # Update the providers mapping
                updates = {
                    "embedding_model": {"advanced": False},
                    "embedding_provider": {"advanced": False},
                    "embedding_choice": {"value": "Embedding Model"},
                }

            # Apply updates to the build_config
            for key, value in updates.items():
                build_config[key].update(value)

        elif field_name == "embedding_choice":
            if field_value == "Astra Vectorize":
                build_config["embedding_model"]["advanced"] = True

                # Update the providers mapping
                vectorize_providers = self.get_vectorize_providers()

                new_parameter = DropdownInput(
                    name="embedding_provider",
                    display_name="Embedding Provider",
                    options=vectorize_providers.keys(),
                    value="",
                    required=True,
                    real_time_refresh=True,
                ).to_dict()

                self.insert_in_dict(build_config, "embedding_choice", {"embedding_provider": new_parameter})
            else:
                build_config["embedding_model"]["advanced"] = False

                self.del_fields(
                    build_config,
                    [
                        "embedding_provider",
                        "model",
                        "z_01_model_parameters",
                        "z_02_api_key_name",
                        "z_03_provider_api_key",
                        "z_04_authentication",
                    ],
                )

        elif field_name == "embedding_provider":
            self.del_fields(
                build_config,
                ["model", "z_01_model_parameters", "z_02_api_key_name", "z_03_provider_api_key", "z_04_authentication"],
            )

            # Update the providers mapping
            vectorize_providers = self.get_vectorize_providers()
            model_options = vectorize_providers[field_value][1]

            new_parameter = DropdownInput(
                name="model",
                display_name="Model",
                info="The embedding model to use for the selected provider. Each provider has a different set of "
                "models available (full list at "
                "https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html):\n\n"
                f"{', '.join(model_options)}",
                options=model_options,
                value=None,
                required=True,
                real_time_refresh=True,
            ).to_dict()

            self.insert_in_dict(build_config, "embedding_provider", {"model": new_parameter})

        elif field_name == "model":
            self.del_fields(
                build_config,
                ["z_01_model_parameters", "z_02_api_key_name", "z_03_provider_api_key", "z_04_authentication"],
            )

            new_parameter_1 = DictInput(
                name="z_01_model_parameters",
                display_name="Model Parameters",
                list=True,
            ).to_dict()

            new_parameter_2 = MessageTextInput(
                name="z_02_api_key_name",
                display_name="API Key Name",
                info="The name of the embeddings provider API key stored on Astra. "
                "If set, it will override the 'ProviderKey' in the authentication parameters.",
            ).to_dict()

            new_parameter_3 = SecretStrInput(
                load_from_db=False,
                name="z_03_provider_api_key",
                display_name="Provider API Key",
                info="An alternative to the Astra Authentication that passes an API key for the provider "
                "with each request to Astra DB. "
                "This may be used when Vectorize is configured for the collection, "
                "but no corresponding provider secret is stored within Astra's key management system.",
            ).to_dict()

            new_parameter_4 = DictInput(
                name="z_04_authentication",
                display_name="Authentication Parameters",
                list=True,
            ).to_dict()

            self.insert_in_dict(
                build_config,
                "model",
                {
                    "z_01_model_parameters": new_parameter_1,
                    "z_02_api_key_name": new_parameter_2,
                    "z_03_provider_api_key": new_parameter_3,
                    "z_04_authentication": new_parameter_4,
                },
            )

        return build_config

    def build_vectorize_options(self, **kwargs):
        for attribute in [
            "embedding_provider",
            "model",
            "z_01_model_parameters",
            "z_02_api_key_name",
            "z_03_provider_api_key",
            "z_04_authentication",
        ]:
            if not hasattr(self, attribute):
                setattr(self, attribute, None)

        # Fetch values from kwargs if any self.* attributes are None
        provider_mapping = self.get_vectorize_providers()
        provider_value = provider_mapping.get(self.embedding_provider, [None])[0] or kwargs.get("embedding_provider")
        model_name = self.model or kwargs.get("model")
        authentication = {**(self.z_04_authentication or {}), **kwargs.get("z_04_authentication", {})}
        parameters = self.z_01_model_parameters or kwargs.get("z_01_model_parameters", {})

        # Set the API key name if provided
        api_key_name = self.z_02_api_key_name or kwargs.get("z_02_api_key_name")
        provider_key = self.z_03_provider_api_key or kwargs.get("z_03_provider_api_key")
        if api_key_name:
            authentication["providerKey"] = api_key_name
        if authentication:
            provider_key = None
            authentication["providerKey"] = authentication["providerKey"].split(".")[0]

        # Set authentication and parameters to None if no values are provided
        if not authentication:
            authentication = None
        if not parameters:
            parameters = None

        return {
            # must match astrapy.info.CollectionVectorServiceOptions
            "collection_vector_service_options": {
                "provider": provider_value,
                "modelName": model_name,
                "authentication": authentication,
                "parameters": parameters,
            },
            "collection_embedding_api_key": provider_key,
        }

    @check_cached_vector_store
    def build_vector_store(self, vectorize_options=None):
        try:
            from langchain_astradb import AstraDBVectorStore
        except ImportError as e:
            msg = (
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )
            raise ImportError(msg) from e

        # Initialize parameters based on the collection name
        is_new_collection = self.get_collection_options() is None

        # Get the embedding model
        embedding_params = {"embedding": self.embedding_model} if self.embedding_choice == "Embedding Model" else {}

        # Use the embedding model if the choice is set to "Embedding Model"
        if self.embedding_choice == "Astra Vectorize" and is_new_collection:
            from astrapy.info import CollectionVectorServiceOptions

            # Build the vectorize options dictionary
            dict_options = vectorize_options or self.build_vectorize_options(
                embedding_provider=getattr(self, "embedding_provider", None) or None,
                model=getattr(self, "model", None) or None,
                z_01_model_parameters=getattr(self, "z_01_model_parameters", None) or None,
                z_02_api_key_name=getattr(self, "z_02_api_key_name", None) or None,
                z_03_provider_api_key=getattr(self, "z_03_provider_api_key", None) or None,
                z_04_authentication=getattr(self, "z_04_authentication", {}) or {},
            )

            # Set the embedding dictionary
            embedding_params = {
                "collection_vector_service_options": CollectionVectorServiceOptions.from_dict(
                    dict_options.get("collection_vector_service_options")
                ),
                "collection_embedding_api_key": dict_options.get("collection_embedding_api_key"),
            }

        # Get the running environment for Langflow
        environment = parse_api_endpoint(self.get_api_endpoint()).environment if self.get_api_endpoint() else None

        # Get Langflow version and platform information
        __version__ = get_version_info()["version"]
        langflow_prefix = ""
        if os.getenv("LANGFLOW_HOST") is not None:
            langflow_prefix = "ds-"

        # Bundle up the auto-detect parameters
        autodetect_params = {
            "autodetect_collection": not is_new_collection,  # TODO: May want to expose this option
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
                collection_name=self.get_collection_choice(),
                environment=environment,
                # Astra DB Usage Tracking Parameters
                ext_callers=[(f"{langflow_prefix}langflow", __version__)],
                # Astra DB Vector Store Parameters
                **autodetect_params or {},
                **embedding_params or {},
                **self.astradb_vectorstore_kwargs or {},
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
