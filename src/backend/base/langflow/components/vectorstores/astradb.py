from collections import defaultdict
from dataclasses import asdict, dataclass, field

from astrapy import AstraDBAdmin, DataAPIClient, Database
from astrapy.info import CollectionDescriptor
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
                        "name": "create_database",
                        "description": "",
                        "display_name": "Create new database",
                        "field_order": ["new_database_name", "cloud_provider", "region"],
                        "template": {
                            "new_database_name": StrInput(
                                name="new_database_name",
                                display_name="Name",
                                info="Name of the new database to create in Astra DB.",
                                required=True,
                            ),
                            "cloud_provider": DropdownInput(
                                name="cloud_provider",
                                display_name="Cloud provider",
                                info="Cloud provider for the new database.",
                                options=["Amazon Web Services", "Google Cloud Platform", "Microsoft Azure"],
                                required=True,
                                real_time_refresh=True,
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
                        "name": "create_collection",
                        "description": "",
                        "display_name": "Create new collection",
                        "field_order": [
                            "new_collection_name",
                            "embedding_generation_provider",
                            "embedding_generation_model",
                            "dimension",
                        ],
                        "template": {
                            "new_collection_name": StrInput(
                                name="new_collection_name",
                                display_name="Name",
                                info="Name of the new collection to create in Astra DB.",
                                required=True,
                            ),
                            "embedding_generation_provider": DropdownInput(
                                name="embedding_generation_provider",
                                display_name="Embedding generation method",
                                info="Provider to use for generating embeddings.",
                                real_time_refresh=True,
                                required=True,
                                options=["Bring your own", "Nvidia"],
                            ),
                            "embedding_generation_model": DropdownInput(
                                name="embedding_generation_model",
                                display_name="Embedding model",
                                info="Model to use for generating embeddings.",
                                required=True,
                                options=[],
                            ),
                            "dimension": IntInput(
                                name="dimension",
                                display_name="Dimensions (Required only for `Bring your own`)",
                                info="Dimensions of the embeddings to generate.",
                                required=False,
                                value=1024,
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
            real_time_refresh=True,
        ),
        DropdownInput(
            name="database_name",
            display_name="Database",
            info="The Database name for the Astra DB instance.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            dialog_inputs=asdict(NewDatabaseInput()),
            combobox=True,
        ),
        StrInput(
            name="api_endpoint",
            display_name="Astra DB API Endpoint",
            info="The API Endpoint for the Astra DB instance. Supercedes database selection.",
            advanced=True,
        ),
        DropdownInput(
            name="collection_name",
            display_name="Collection",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
            refresh_button=True,
            real_time_refresh=True,
            dialog_inputs=asdict(NewCollectionInput()),
            combobox=True,
            advanced=True,
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
        BoolInput(
            name="autodetect_collection",
            display_name="Autodetect Collection",
            info="Boolean flag to determine whether to autodetect the collection.",
            advanced=True,
            value=True,
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
        # TODO: Programmatically fetch the regions for each cloud provider
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
    def get_vectorize_providers(cls, token: str, environment: str | None = None, api_endpoint: str | None = None):
        try:
            # Get the admin object
            admin = AstraDBAdmin(token=token, environment=environment)
            db_admin = admin.get_database_admin(api_endpoint=api_endpoint)

            # Get the list of embedding providers
            embedding_providers = db_admin.find_embedding_providers().as_dict()

            vectorize_providers_mapping = {}
            # Map the provider display name to the provider key and models
            for provider_key, provider_data in embedding_providers["embeddingProviders"].items():
                # Get the provider display name and models
                display_name = provider_data["displayName"]
                models = [model["name"] for model in provider_data["models"]]

                # Build our mapping
                vectorize_providers_mapping[display_name] = [provider_key, models]

            # Sort the resulting dictionary
            return defaultdict(list, dict(sorted(vectorize_providers_mapping.items())))
        except Exception as e:
            msg = f"Error fetching vectorize providers: {e}"
            raise ValueError(msg) from e

    @classmethod
    async def create_database_api(
        cls,
        new_database_name: str,
        cloud_provider: str,
        region: str,
        token: str,
        environment: str | None = None,
        keyspace: str | None = None,
    ):
        client = DataAPIClient(token=token, environment=environment)

        # Get the admin object
        admin_client = client.get_admin(token=token)

        # Call the create database function
        return await admin_client.async_create_database(
            name=new_database_name,
            cloud_provider=cls.map_cloud_providers()[cloud_provider]["id"],
            region=region,
            keyspace=keyspace,
            wait_until_active=False,
        )

    @classmethod
    async def create_collection_api(
        cls,
        new_collection_name: str,
        token: str,
        api_endpoint: str,
        environment: str | None = None,
        keyspace: str | None = None,
        dimension: int | None = None,
        embedding_generation_provider: str | None = None,
        embedding_generation_model: str | None = None,
    ):
        # Create the data API client
        client = DataAPIClient(token=token, environment=environment)

        # Get the database object
        database = client.get_async_database(api_endpoint=api_endpoint, token=token)

        # Build vectorize options, if needed
        vectorize_options = None
        if not dimension:
            vectorize_options = CollectionVectorServiceOptions(
                provider=cls.get_vectorize_providers(
                    token=token, environment=environment, api_endpoint=api_endpoint
                ).get(embedding_generation_provider, [None, []])[0],
                model_name=embedding_generation_model,
            )

        # Create the collection
        return await database.create_collection(
            name=new_collection_name,
            keyspace=keyspace,
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

        # Set the environment properly
        env_string = ""
        if environment and environment != "prod":
            env_string = f"-{environment}"

        # Generate the api endpoint for each database
        db_info_dict = {}
        for db in db_list:
            try:
                # Get the API endpoint for the database
                api_endpoint = f"https://{db.info.id}-{db.info.region}.apps.astra{env_string}.datastax.com"

                # Get the number of collections
                try:
                    num_collections = len(
                        list(
                            client.get_database(
                                api_endpoint=api_endpoint, token=token, keyspace=db.info.keyspace
                            ).list_collection_names(keyspace=db.info.keyspace)
                        )
                    )
                except Exception:  # noqa: BLE001
                    num_collections = 0
                    if db.status != "PENDING":
                        continue

                # Add the database to the dictionary
                db_info_dict[db.info.name] = {
                    "api_endpoint": api_endpoint,
                    "collections": num_collections,
                    "status": db.status if db.status != "ACTIVE" else None,
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
        api_endpoint: str | None = None,
        database_name: str | None = None,
    ):
        # If the api_endpoint is set, return it
        if api_endpoint:
            return api_endpoint

        # Check if the database_name is like a url
        if database_name and database_name.startswith("https://"):
            return database_name

        # If the database is not set, nothing we can do.
        if not database_name:
            return None

        # Grab the database object
        db = cls.get_database_list_static(token=token, environment=environment).get(database_name)
        if not db:
            return None

        # Otherwise, get the URL from the database list
        return db.get("api_endpoint")

    def get_api_endpoint(self):
        return self.get_api_endpoint_static(
            token=self.token,
            environment=self.environment,
            api_endpoint=self.api_endpoint,
            database_name=self.database_name,
        )

    def get_keyspace(self):
        keyspace = self.keyspace

        if keyspace:
            return keyspace.strip()

        return None

    def get_database_object(self, api_endpoint: str | None = None):
        try:
            client = DataAPIClient(token=self.token, environment=self.environment)

            return client.get_database(
                api_endpoint=api_endpoint or self.get_api_endpoint(),
                token=self.token,
                keyspace=self.get_keyspace(),
            )
        except Exception as e:
            msg = f"Error fetching database object: {e}"
            raise ValueError(msg) from e

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

    def _initialize_database_options(self):
        try:
            return [
                {
                    "name": name,
                    "status": info["status"],
                    "collections": info["collections"],
                    "api_endpoint": info["api_endpoint"],
                    "icon": "data",
                }
                for name, info in self.get_database_list().items()
            ]
        except Exception as e:
            msg = f"Error fetching database options: {e}"
            raise ValueError(msg) from e

    @classmethod
    def get_provider_icon(cls, collection: CollectionDescriptor | None = None, provider_name: str | None = None) -> str:
        # Get the provider name from the collection
        provider_name = provider_name or (
            collection.options.vector.service.provider
            if collection and collection.options and collection.options.vector and collection.options.vector.service
            else None
        )

        # If there is no provider, use the vector store icon
        if not provider_name or provider_name == "bring your own":
            return "vectorstores"

        # Special case for certain models
        # TODO: Add more icons
        if provider_name == "nvidia":
            return "NVIDIA"
        if provider_name == "openai":
            return "OpenAI"

        # Title case on the provider for the icon if no special case
        return provider_name.title()

    def _initialize_collection_options(self, api_endpoint: str | None = None):
        # Nothing to generate if we don't have an API endpoint yet
        api_endpoint = api_endpoint or self.get_api_endpoint()
        if not api_endpoint:
            return []

        # Retrieve the database object
        database = self.get_database_object(api_endpoint=api_endpoint)

        # Get the list of collections
        collection_list = list(database.list_collections(keyspace=self.get_keyspace()))

        # Return the list of collections and metadata associated
        return [
            {
                "name": col.name,
                "records": self.collection_data(collection_name=col.name, database=database),
                "provider": (
                    col.options.vector.service.provider if col.options.vector and col.options.vector.service else None
                ),
                "icon": self.get_provider_icon(collection=col),
                "model": (
                    col.options.vector.service.model_name if col.options.vector and col.options.vector.service else None
                ),
            }
            for col in collection_list
        ]

    def reset_provider_options(self, build_config: dict):
        # Get the list of vectorize providers
        vectorize_providers = self.get_vectorize_providers(
            token=self.token,
            environment=self.environment,
            api_endpoint=build_config["api_endpoint"]["value"],
        )

        # Append a special case for Bring your own
        vectorize_providers["Bring your own"] = [None, ["Bring your own"]]

        # If the collection is set, allow user to see embedding options
        build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
            "embedding_generation_provider"
        ]["options"] = ["Bring your own", "Nvidia", *[key for key in vectorize_providers if key != "Nvidia"]]

        # For all not Bring your own or Nvidia providers, add metadata saying configure in Astra DB Portal
        provider_options = build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
            "embedding_generation_provider"
        ]["options"]

        # Go over each possible provider and add metadata to configure in Astra DB Portal
        for provider in provider_options:
            # Skip Bring your own and Nvidia, automatically configured
            if provider in {"Bring your own", "Nvidia"}:
                build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
                    "embedding_generation_provider"
                ]["options_metadata"].append({"icon": self.get_provider_icon(provider_name=provider.lower())})
                continue

            # Add metadata to configure in Astra DB Portal
            build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
                "embedding_generation_provider"
            ]["options_metadata"].append({" ": "Configure in Astra DB Portal"})

        # And allow the user to see the models based on a selected provider
        embedding_provider = build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
            "embedding_generation_provider"
        ]["value"]

        # Set the options for the embedding model based on the provider
        build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"][
            "embedding_generation_model"
        ]["options"] = vectorize_providers.get(embedding_provider, [[], []])[1]

        return build_config

    def reset_collection_list(self, build_config: dict):
        # Get the list of options we have based on the token provided
        collection_options = self._initialize_collection_options(api_endpoint=build_config["api_endpoint"]["value"])

        # If we retrieved options based on the token, show the dropdown
        build_config["collection_name"]["options"] = [col["name"] for col in collection_options]
        build_config["collection_name"]["options_metadata"] = [
            {k: v for k, v in col.items() if k != "name"} for col in collection_options
        ]

        # Reset the selected collection
        if build_config["collection_name"]["value"] not in build_config["collection_name"]["options"]:
            build_config["collection_name"]["value"] = ""

        # If we have a database, collection name should not be advanced
        build_config["collection_name"]["advanced"] = not build_config["database_name"]["value"]

        return build_config

    def reset_database_list(self, build_config: dict):
        # Get the list of options we have based on the token provided
        database_options = self._initialize_database_options()

        # If we retrieved options based on the token, show the dropdown
        build_config["database_name"]["options"] = [db["name"] for db in database_options]
        build_config["database_name"]["options_metadata"] = [
            {k: v for k, v in db.items() if k != "name"} for db in database_options
        ]

        # Reset the selected database
        if build_config["database_name"]["value"] not in build_config["database_name"]["options"]:
            build_config["database_name"]["value"] = ""
            build_config["api_endpoint"]["value"] = ""
            build_config["collection_name"]["advanced"] = True

        # If we have a token, database name should not be advanced
        build_config["database_name"]["advanced"] = not build_config["token"]["value"]

        return build_config

    def reset_build_config(self, build_config: dict):
        # Reset the list of databases we have based on the token provided
        build_config["database_name"]["options"] = []
        build_config["database_name"]["options_metadata"] = []
        build_config["database_name"]["value"] = ""
        build_config["database_name"]["advanced"] = True
        build_config["api_endpoint"]["value"] = ""

        # Reset the list of collections and metadata associated
        build_config["collection_name"]["options"] = []
        build_config["collection_name"]["options_metadata"] = []
        build_config["collection_name"]["value"] = ""
        build_config["collection_name"]["advanced"] = True

        return build_config

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        # Callback for database creation
        if field_name == "database_name" and isinstance(field_value, dict) and "new_database_name" in field_value:
            try:
                await self.create_database_api(
                    new_database_name=field_value["new_database_name"],
                    token=self.token,
                    keyspace=self.get_keyspace(),
                    environment=self.environment,
                    cloud_provider=field_value["cloud_provider"],
                    region=field_value["region"],
                )
            except Exception as e:
                msg = f"Error creating database: {e}"
                raise ValueError(msg) from e

            # Add the new database to the list of options
            build_config["database_name"]["options"] += [field_value["new_database_name"]]
            build_config["database_name"]["options_metadata"] += [{"status": "PENDING"}]

            return self.reset_collection_list(build_config)

        # This is the callback required to update the list of regions for a cloud provider
        if field_name == "database_name" and isinstance(field_value, dict) and "new_database_name" not in field_value:
            cloud_provider = field_value["cloud_provider"]
            build_config["database_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]["region"][
                "options"
            ] = self.map_cloud_providers()[cloud_provider]["regions"]

            return build_config

        # Callback for the creation of collections
        if field_name == "collection_name" and isinstance(field_value, dict) and "new_collection_name" in field_value:
            try:
                # Get the dimension if its a BYO provider
                dimension = (
                    field_value["dimension"]
                    if field_value["embedding_generation_provider"] == "Bring your own"
                    else None
                )

                # Create the collection
                await self.create_collection_api(
                    new_collection_name=field_value["new_collection_name"],
                    token=self.token,
                    api_endpoint=build_config["api_endpoint"]["value"],
                    environment=self.environment,
                    keyspace=self.get_keyspace(),
                    dimension=dimension,
                    embedding_generation_provider=field_value["embedding_generation_provider"],
                    embedding_generation_model=field_value["embedding_generation_model"],
                )
            except Exception as e:
                msg = f"Error creating collection: {e}"
                raise ValueError(msg) from e

            # Add the new collection to the list of options
            build_config["collection_name"]["value"] = field_value["new_collection_name"]
            build_config["collection_name"]["options"].append(field_value["new_collection_name"])

            # Get the provider and model for the new collection
            generation_provider = field_value["embedding_generation_provider"]
            provider = generation_provider if generation_provider != "Bring your own" else None
            generation_model = field_value["embedding_generation_model"]
            model = generation_model if generation_model and generation_model != "Bring your own" else None

            # Set the embedding choice
            build_config["embedding_choice"]["value"] = "Astra Vectorize" if provider else "Embedding Model"
            build_config["embedding_model"]["advanced"] = bool(provider)

            # Add the new collection to the list of options
            icon = "NVIDIA" if provider == "Nvidia" else "vectorstores"
            build_config["collection_name"]["options_metadata"] += [
                {"records": 0, "provider": provider, "icon": icon, "model": model}
            ]

            return build_config

        # Callback to update the model list based on the embedding provider
        if (
            field_name == "collection_name"
            and isinstance(field_value, dict)
            and "new_collection_name" not in field_value
        ):
            return self.reset_provider_options(build_config)

        # When the component first executes, this is the update refresh call
        first_run = field_name == "collection_name" and not field_value and not build_config["database_name"]["options"]

        # If the token has not been provided, simply return the empty build config
        if not self.token:
            return self.reset_build_config(build_config)

        # If this is the first execution of the component, reset and build database list
        if first_run or field_name in {"token", "environment"}:
            return self.reset_database_list(build_config)

        # Refresh the collection name options
        if field_name == "database_name" and not isinstance(field_value, dict):
            # If missing, refresh the database options
            if field_value not in build_config["database_name"]["options"]:
                build_config = await self.update_build_config(build_config, field_value=self.token, field_name="token")
                build_config["database_name"]["value"] = ""
            else:
                # Find the position of the selected database to align with metadata
                index_of_name = build_config["database_name"]["options"].index(field_value)

                # Initializing database condition
                pending = build_config["database_name"]["options_metadata"][index_of_name]["status"] == "PENDING"
                if pending:
                    return self.update_build_config(build_config, field_value=self.token, field_name="token")

                # Set the API endpoint based on the selected database
                build_config["api_endpoint"]["value"] = build_config["database_name"]["options_metadata"][
                    index_of_name
                ]["api_endpoint"]

                # Reset the provider options
                build_config = self.reset_provider_options(build_config)

            # Reset the list of collections we have based on the token provided
            return self.reset_collection_list(build_config)

        # Hide embedding model option if opriona_metadata provider is not null
        if field_name == "collection_name" and not isinstance(field_value, dict):
            # Assume we will be autodetecting the collection:
            build_config["autodetect_collection"]["value"] = True

            # Reload the collection list
            build_config = self.reset_collection_list(build_config)

            # Set the options for collection name to be the field value if its a new collection
            if field_value and field_value not in build_config["collection_name"]["options"]:
                # Add the new collection to the list of options
                build_config["collection_name"]["options"].append(field_value)
                build_config["collection_name"]["options_metadata"].append(
                    {
                        "records": 0,
                        "provider": None,
                        "icon": "",
                        "model": None,
                    }
                )

                # Ensure that autodetect collection is set to False, since its a new collection
                build_config["autodetect_collection"]["value"] = False

            # If nothing is selected, can't detect provider - return
            if not field_value:
                return build_config

            # Find the position of the selected collection to align with metadata
            index_of_name = build_config["collection_name"]["options"].index(field_value)
            value_of_provider = build_config["collection_name"]["options_metadata"][index_of_name]["provider"]

            # If we were able to determine the Vectorize provider, set it accordingly
            if value_of_provider:
                build_config["embedding_model"]["advanced"] = True
                build_config["embedding_choice"]["value"] = "Astra Vectorize"
            else:
                build_config["embedding_model"]["advanced"] = False
                build_config["embedding_choice"]["value"] = "Embedding Model"

            return build_config

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

        # Attempt to build the Vector Store object
        try:
            vector_store = AstraDBVectorStore(
                # Astra DB Authentication Parameters
                token=self.token,
                api_endpoint=database.api_endpoint,
                namespace=database.keyspace,
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

        # Add documents to the vector store
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
                collection = database.get_collection(self.collection_name, keyspace=database.keyspace)
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
