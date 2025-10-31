import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from astrapy import DataAPIClient, Database
from langchain_astradb.utils.astradb import _AstraDBCollectionEnvironment

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    StrInput,
)
from lfx.log.logger import logger


class AstraDBBaseComponent(Component):
    """Base class for AstraDB components with common functionality."""

    @dataclass
    class NewDatabaseInput:
        functionality: str = "create"
        fields: dict[str, dict] = field(
            default_factory=lambda: {
                "data": {
                    "node": {
                        "name": "create_database",
                        "description": "Please allow several minutes for creation to complete.",
                        "display_name": "Create new database",
                        "field_order": ["01_new_database_name", "02_cloud_provider", "03_region"],
                        "template": {
                            "01_new_database_name": StrInput(
                                name="new_database_name",
                                display_name="Name",
                                info="Name of the new database to create in Astra DB.",
                                required=True,
                            ),
                            "02_cloud_provider": DropdownInput(
                                name="cloud_provider",
                                display_name="Cloud provider",
                                info="Cloud provider for the new database.",
                                options=[],
                                required=True,
                                real_time_refresh=True,
                            ),
                            "03_region": DropdownInput(
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
                        "description": "Please allow several seconds for creation to complete.",
                        "display_name": "Create new collection",
                        "field_order": [
                            "01_new_collection_name",
                            "02_embedding_generation_provider",
                            "03_embedding_generation_model",
                            "04_dimension",
                        ],
                        "template": {
                            "01_new_collection_name": StrInput(
                                name="new_collection_name",
                                display_name="Name",
                                info="Name of the new collection to create in Astra DB.",
                                required=True,
                            ),
                            "02_embedding_generation_provider": DropdownInput(
                                name="embedding_generation_provider",
                                display_name="Embedding generation method",
                                info="Provider to use for generating embeddings.",
                                helper_text=(
                                    "To create collections with more embedding provider options, go to "
                                    '<a class="underline" href="https://astra.datastax.com/" target=" _blank" '
                                    'rel="noopener noreferrer">your database in Astra DB</a>'
                                ),
                                real_time_refresh=True,
                                required=True,
                                options=[],
                            ),
                            "03_embedding_generation_model": DropdownInput(
                                name="embedding_generation_model",
                                display_name="Embedding model",
                                info="Model to use for generating embeddings.",
                                real_time_refresh=True,
                                options=[],
                            ),
                            "04_dimension": IntInput(
                                name="dimension",
                                display_name="Dimensions",
                                info="Dimensions of the embeddings to generate.",
                                value=None,
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
        DropdownInput(
            name="environment",
            display_name="Environment",
            info="The environment for the Astra DB API Endpoint.",
            options=["prod", "test", "dev"],
            value="prod",
            advanced=True,
            real_time_refresh=True,
            combobox=True,
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
        DropdownInput(
            name="api_endpoint",
            display_name="Astra DB API Endpoint",
            info="The API Endpoint for the Astra DB instance. Supercedes database selection.",
            advanced=True,
        ),
        DropdownInput(
            name="keyspace",
            display_name="Keyspace",
            info="Optional keyspace within Astra DB to use for the collection.",
            advanced=True,
            options=[],
            real_time_refresh=True,
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
            show=False,
        ),
        BoolInput(
            name="autodetect_collection",
            display_name="Autodetect Collection",
            info="Boolean flag to determine whether to autodetect the collection.",
            advanced=True,
            value=True,
        ),
    ]

    @classmethod
    def get_environment(cls, environment: str | None = None) -> str:
        if not environment:
            return "prod"
        return environment

    @classmethod
    def map_cloud_providers(cls, token: str, environment: str | None = None) -> dict[str, dict[str, Any]]:
        """Fetch all available cloud providers and regions."""
        # Get the admin object
        client = DataAPIClient(environment=cls.get_environment(environment))
        admin_client = client.get_admin(token=token)

        # Get the list of available regions
        available_regions = admin_client.find_available_regions(only_org_enabled_regions=True)

        provider_mapping: dict[str, dict[str, str]] = {
            "AWS": {"name": "Amazon Web Services", "id": "aws"},
            "GCP": {"name": "Google Cloud Platform", "id": "gcp"},
            "Azure": {"name": "Microsoft Azure", "id": "azure"},
        }

        result: dict[str, dict[str, Any]] = {}
        for region_info in available_regions:
            cloud_provider = region_info.cloud_provider
            region = region_info.name

            if cloud_provider in provider_mapping:
                provider_name = provider_mapping[cloud_provider]["name"]
                provider_id = provider_mapping[cloud_provider]["id"]

                if provider_name not in result:
                    result[provider_name] = {"id": provider_id, "regions": []}

                result[provider_name]["regions"].append(region)

        return result

    @classmethod
    def get_vectorize_providers(cls, token: str, environment: str | None = None, api_endpoint: str | None = None):
        try:
            # Get the admin object
            client = DataAPIClient(environment=cls.get_environment(environment))
            admin_client = client.get_admin()
            db_admin = admin_client.get_database_admin(api_endpoint, token=token)

            # Get the list of embedding providers
            embedding_providers = db_admin.find_embedding_providers()

            vectorize_providers_mapping = {}
            # Map the provider display name to the provider key and models
            for provider_key, provider_data in embedding_providers.embedding_providers.items():
                # Get the provider display name and models
                display_name = provider_data.display_name
                models = [model.name for model in provider_data.models]

                # Build our mapping
                vectorize_providers_mapping[display_name] = [provider_key, models]

            # Sort the resulting dictionary
            return defaultdict(list, dict(sorted(vectorize_providers_mapping.items())))
        except Exception as _:  # noqa: BLE001
            return {}

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
        # Get the environment, set to prod if null like
        my_env = cls.get_environment(environment)

        # Initialize the Data API client
        client = DataAPIClient(environment=my_env)

        # Get the admin object
        admin_client = client.get_admin(token=token)

        # Raise a value error if name isn't provided
        if not new_database_name:
            msg = "Database name is required to create a new database."
            raise ValueError(msg)

        # Call the create database function
        return await admin_client.async_create_database(
            name=new_database_name,
            cloud_provider=cls.map_cloud_providers(token=token, environment=my_env)[cloud_provider]["id"],
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
        # Build vectorize options, if needed
        vectorize_options = None
        if not dimension:
            try:
                from langchain_astradb import VectorServiceOptions
            except ImportError as e:
                msg = (
                    "langchain-astradb is required to create AstraDB collections with "
                    "Astra Vectorize embeddings. Please install it with "
                    "`pip install langchain-astradb`."
                )
                raise ImportError(msg) from e

            environment = cls.get_environment(environment)
            providers = cls.get_vectorize_providers(token=token, environment=environment, api_endpoint=api_endpoint)
            vectorize_options = VectorServiceOptions(
                provider=providers.get(embedding_generation_provider, [None, []])[0],
                model_name=embedding_generation_model,
            )

        # Raise a value error if name isn't provided
        if not new_collection_name:
            msg = "Collection name is required to create a new collection."
            raise ValueError(msg)

        # Define the base arguments being passed to the create collection function
        base_args = {
            "collection_name": new_collection_name,
            "token": token,
            "api_endpoint": api_endpoint,
            "keyspace": keyspace,
            "environment": environment,
            "embedding_dimension": dimension,
            "collection_vector_service_options": vectorize_options,
        }

        _AstraDBCollectionEnvironment(**base_args)

    @classmethod
    def get_database_list_static(cls, token: str, environment: str | None = None):
        environment = cls.get_environment(environment)
        client = DataAPIClient(environment=environment)

        # Get the admin object
        admin_client = client.get_admin(token=token)

        # Get the list of databases
        db_list = admin_client.list_databases()

        # Generate the api endpoint for each database
        db_info_dict = {}
        for db in db_list:
            try:
                # Get the API endpoint for the database
                api_endpoints = [db_reg.api_endpoint for db_reg in db.regions]

                # Get the number of collections
                try:
                    # Get the number of collections in the database
                    num_collections = len(
                        client.get_database(
                            api_endpoints[0],
                            token=token,
                        ).list_collection_names()
                    )
                except Exception:  # noqa: BLE001
                    if db.status != "PENDING":
                        continue
                    num_collections = 0

                # Add the database to the dictionary
                db_info_dict[db.name] = {
                    "api_endpoints": api_endpoints,
                    "keyspaces": db.keyspaces,
                    "collections": num_collections,
                    "status": db.status if db.status != "ACTIVE" else None,
                    "org_id": db.org_id if db.org_id else None,
                }
            except Exception as e:  # noqa: BLE001
                logger.debug("Failed to get metadata for database %s: %s", db.name, e)

        return db_info_dict

    def get_database_list(self):
        return self.get_database_list_static(
            token=self.token,
            environment=self.environment,
        )

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
        environment = cls.get_environment(environment)
        db = cls.get_database_list_static(token=token, environment=environment).get(database_name)
        if not db:
            return None

        # Otherwise, get the URL from the database list
        endpoints = db.get("api_endpoints") or []
        return endpoints[0] if endpoints else None

    def get_api_endpoint(self):
        return self.get_api_endpoint_static(
            token=self.token,
            environment=self.environment,
            api_endpoint=self.api_endpoint,
            database_name=self.database_name,
        )

    @classmethod
    def get_database_id_static(cls, api_endpoint: str) -> str | None:
        # Pattern matches standard UUID format: 8-4-4-4-12 hexadecimal characters
        uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        match = re.search(uuid_pattern, api_endpoint)

        return match.group(0) if match else None

    def get_database_id(self):
        return self.get_database_id_static(api_endpoint=self.get_api_endpoint())

    def get_keyspace(self):
        keyspace = self.keyspace

        if keyspace:
            return keyspace.strip()

        return "default_keyspace"

    def get_database_object(self, api_endpoint: str | None = None):
        try:
            client = DataAPIClient(environment=self.environment)

            return client.get_database(
                api_endpoint or self.get_api_endpoint(),
                token=self.token,
                keyspace=self.get_keyspace(),
            )
        except Exception as e:
            msg = f"Error fetching database object: {e}"
            raise ValueError(msg) from e

    def collection_data(self, collection_name: str, database: Database = None):
        try:
            if not database:
                client = DataAPIClient(environment=self.environment)

                database = client.get_database(
                    self.get_api_endpoint(),
                    token=self.token,
                    keyspace=self.get_keyspace(),
                )

            collection = database.get_collection(collection_name)

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
                    "api_endpoints": info["api_endpoints"],
                    "keyspaces": info["keyspaces"],
                    "org_id": info["org_id"],
                }
                for name, info in self.get_database_list().items()
            ]
        except Exception as e:
            msg = f"Error fetching database options: {e}"
            raise ValueError(msg) from e

    @classmethod
    def get_provider_icon(cls, collection=None, provider_name: str | None = None) -> str:
        # Get the provider name from the collection
        provider_name = provider_name or (
            collection.definition.vector.service.provider
            if (
                collection
                and collection.definition
                and collection.definition.vector
                and collection.definition.vector.service
            )
            else None
        )

        # If there is no provider, use the vector store icon
        if not provider_name or provider_name.lower() == "bring your own":
            return "vectorstores"

        # Map provider casings
        case_map = {
            "nvidia": "NVIDIA",
            "openai": "OpenAI",
            "amazon bedrock": "AmazonBedrockEmbeddings",
            "azure openai": "AzureOpenAiEmbeddings",
            "cohere": "Cohere",
            "jina ai": "JinaAI",
            "mistral ai": "MistralAI",
            "upstage": "Upstage",
            "voyage ai": "VoyageAI",
        }

        # Adjust the casing on some like nvidia
        return case_map[provider_name.lower()] if provider_name.lower() in case_map else provider_name.title()

    def _initialize_collection_options(self, api_endpoint: str | None = None):
        # Nothing to generate if we don't have an API endpoint yet
        api_endpoint = api_endpoint or self.get_api_endpoint()
        if not api_endpoint:
            return []

        # Retrieve the database object
        database = self.get_database_object(api_endpoint=api_endpoint)

        # Get the list of collections
        collection_list = database.list_collections(keyspace=self.get_keyspace())

        # Return the list of collections and metadata associated
        return [
            {
                "name": col.name,
                "records": self.collection_data(collection_name=col.name, database=database),
                "provider": (
                    col.definition.vector.service.provider
                    if col.definition.vector and col.definition.vector.service
                    else None
                ),
                "icon": self.get_provider_icon(collection=col),
                "model": (
                    col.definition.vector.service.model_name
                    if col.definition.vector and col.definition.vector.service
                    else None
                ),
            }
            for col in collection_list
        ]

    def reset_provider_options(self, build_config: dict) -> dict:
        """Reset provider options and related configurations in the build_config dictionary."""
        # Extract template path for cleaner access
        template = build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]

        # Get vectorize providers
        vectorize_providers_api = self.get_vectorize_providers(
            token=self.token,
            environment=self.environment,
            api_endpoint=build_config["api_endpoint"]["value"],
        )

        # Create a new dictionary with "Bring your own" first
        vectorize_providers: dict[str, list[list[str]]] = {"Bring your own": [[], []]}

        # Add the remaining items (only Nvidia) from the original dictionary
        vectorize_providers.update(
            {
                k: v
                for k, v in vectorize_providers_api.items()
                if k.lower() in ["nvidia"]  # TODO: Eventually support more
            }
        )

        # Set provider options
        provider_field = "02_embedding_generation_provider"
        template[provider_field]["options"] = list(vectorize_providers.keys())

        # Add metadata for each provider option
        template[provider_field]["options_metadata"] = [
            {"icon": self.get_provider_icon(provider_name=provider)} for provider in template[provider_field]["options"]
        ]

        # Get selected embedding provider
        embedding_provider = template[provider_field]["value"]
        is_bring_your_own = embedding_provider and embedding_provider == "Bring your own"

        # Configure embedding model field
        model_field = "03_embedding_generation_model"
        template[model_field].update(
            {
                "options": vectorize_providers.get(embedding_provider, [[], []])[1],
                "placeholder": "Bring your own" if is_bring_your_own else None,
                "readonly": is_bring_your_own,
                "required": not is_bring_your_own,
                "value": None,
            }
        )

        # If this is a bring your own, set dimensions to 0
        return self.reset_dimension_field(build_config)

    def reset_dimension_field(self, build_config: dict) -> dict:
        """Reset dimension field options based on provided configuration."""
        # Extract template path for cleaner access
        template = build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]

        # Get selected embedding model
        provider_field = "02_embedding_generation_provider"
        embedding_provider = template[provider_field]["value"]
        is_bring_your_own = embedding_provider and embedding_provider == "Bring your own"

        # Configure dimension field
        dimension_field = "04_dimension"
        dimension_value = 1024 if not is_bring_your_own else None  # TODO: Dynamically figure this out
        template[dimension_field].update(
            {
                "placeholder": dimension_value,
                "value": dimension_value,
                "readonly": not is_bring_your_own,
                "required": is_bring_your_own,
            }
        )

        return build_config

    def reset_collection_list(self, build_config: dict) -> dict:
        """Reset collection list options based on provided configuration."""
        # Get collection options
        collection_options = self._initialize_collection_options(api_endpoint=build_config["api_endpoint"]["value"])
        # Update collection configuration
        collection_config = build_config["collection_name"]
        collection_config.update(
            {
                "options": [col["name"] for col in collection_options],
                "options_metadata": [{k: v for k, v in col.items() if k != "name"} for col in collection_options],
            }
        )

        # Reset selected collection if not in options
        if collection_config["value"] not in collection_config["options"]:
            collection_config["value"] = ""

        # Set advanced status based on database selection
        collection_config["show"] = bool(build_config["database_name"]["value"])

        return build_config

    def reset_database_list(self, build_config: dict) -> dict:
        """Reset database list options and related configurations."""
        # Get database options
        database_options = self._initialize_database_options()

        # Update cloud provider options
        template = build_config["database_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]
        template["02_cloud_provider"]["options"] = list(
            self.map_cloud_providers(
                token=self.token,
                environment=self.environment,
            ).keys()
        )

        # Update database configuration
        database_config = build_config["database_name"]
        database_config.update(
            {
                "options": [db["name"] for db in database_options],
                "options_metadata": [{k: v for k, v in db.items() if k != "name"} for db in database_options],
            }
        )

        # Reset selections if value not in options
        if database_config["value"] not in database_config["options"]:
            database_config["value"] = ""
            build_config["api_endpoint"]["options"] = []
            build_config["api_endpoint"]["value"] = ""
            build_config["collection_name"]["show"] = False

        # Set advanced status based on token presence
        database_config["show"] = bool(build_config["token"]["value"])

        return build_config

    def reset_build_config(self, build_config: dict) -> dict:
        """Reset all build configuration options to default empty state."""
        # Reset database configuration
        database_config = build_config["database_name"]
        database_config.update({"options": [], "options_metadata": [], "value": "", "show": False})
        build_config["api_endpoint"]["options"] = []
        build_config["api_endpoint"]["value"] = ""

        # Reset collection configuration
        collection_config = build_config["collection_name"]
        collection_config.update({"options": [], "options_metadata": [], "value": "", "show": False})

        return build_config

    async def update_build_config(
        self,
        build_config: dict,
        field_value: str | dict,
        field_name: str | None = None,
    ) -> dict:
        """Update build configuration based on field name and value."""
        # Early return if no token provided
        if not self.token:
            return self.reset_build_config(build_config)

        # Database creation callback
        if field_name == "database_name" and isinstance(field_value, dict):
            if "01_new_database_name" in field_value:
                await self._create_new_database(build_config, field_value)
                return self.reset_collection_list(build_config)
            return self._update_cloud_regions(build_config, field_value)

        # Collection creation callback
        if field_name == "collection_name" and isinstance(field_value, dict):
            # Case 1: New collection creation
            if "01_new_collection_name" in field_value:
                await self._create_new_collection(build_config, field_value)
                return build_config

            # Case 2: Update embedding provider options
            if "02_embedding_generation_provider" in field_value:
                return self.reset_provider_options(build_config)

            # Case 3: Update dimension field
            if "03_embedding_generation_model" in field_value:
                return self.reset_dimension_field(build_config)

        # Initial execution or token/environment change
        first_run = field_name == "collection_name" and not field_value and not build_config["database_name"]["options"]
        if first_run or field_name in {"token", "environment"}:
            return self.reset_database_list(build_config)

        # Database selection change
        if field_name == "database_name" and not isinstance(field_value, dict):
            return self._handle_database_selection(build_config, field_value)

        # Keyspace selection change
        if field_name == "keyspace":
            return self.reset_collection_list(build_config)

        # Collection selection change
        if field_name == "collection_name" and not isinstance(field_value, dict):
            return self._handle_collection_selection(build_config, field_value)

        return build_config

    async def _create_new_database(self, build_config: dict, field_value: dict) -> None:
        """Create a new database and update build config options."""
        try:
            await self.create_database_api(
                new_database_name=field_value["01_new_database_name"],
                token=self.token,
                keyspace=self.get_keyspace(),
                environment=self.environment,
                cloud_provider=field_value["02_cloud_provider"],
                region=field_value["03_region"],
            )
        except Exception as e:
            msg = f"Error creating database: {e}"
            raise ValueError(msg) from e

        build_config["database_name"]["options"].append(field_value["01_new_database_name"])
        build_config["database_name"]["options_metadata"].append(
            {
                "status": "PENDING",
                "collections": 0,
                "api_endpoints": [],
                "keyspaces": [self.get_keyspace()],
                "org_id": None,
            }
        )

    def _update_cloud_regions(self, build_config: dict, field_value: dict) -> dict:
        """Update cloud provider regions in build config."""
        cloud_provider = field_value["02_cloud_provider"]

        # Update the region options based on the selected cloud provider
        template = build_config["database_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]
        template["03_region"]["options"] = self.map_cloud_providers(
            token=self.token,
            environment=self.environment,
        )[cloud_provider]["regions"]

        # Reset the the 03_region value if it's not in the new options
        if template["03_region"]["value"] not in template["03_region"]["options"]:
            template["03_region"]["value"] = None

        return build_config

    async def _create_new_collection(self, build_config: dict, field_value: dict) -> None:
        """Create a new collection and update build config options."""
        embedding_provider = field_value.get("02_embedding_generation_provider")
        try:
            await self.create_collection_api(
                new_collection_name=field_value["01_new_collection_name"],
                token=self.token,
                api_endpoint=build_config["api_endpoint"]["value"],
                environment=self.environment,
                keyspace=self.get_keyspace(),
                dimension=field_value.get("04_dimension") if embedding_provider == "Bring your own" else None,
                embedding_generation_provider=embedding_provider,
                embedding_generation_model=field_value.get("03_embedding_generation_model"),
            )
        except Exception as e:
            msg = f"Error creating collection: {e}"
            raise ValueError(msg) from e

        provider = embedding_provider.lower() if embedding_provider and embedding_provider != "Bring your own" else None
        build_config["collection_name"].update(
            {
                "value": field_value["01_new_collection_name"],
                "options": build_config["collection_name"]["options"] + [field_value["01_new_collection_name"]],
            }
        )

        # Update collection metadata
        build_config["collection_name"]["options_metadata"].append(
            {
                "records": 0,
                "provider": provider,
                "icon": self.get_provider_icon(provider_name=provider),
                "model": field_value.get("03_embedding_generation_model"),
            }
        )

    def _handle_database_selection(self, build_config: dict, field_value: str) -> dict:
        """Handle database selection and update related configurations."""
        build_config = self.reset_database_list(build_config)

        # Reset collection list if database selection changes
        if field_value not in build_config["database_name"]["options"]:
            build_config["database_name"]["value"] = ""
            return build_config

        # Get the api endpoint for the selected database
        index = build_config["database_name"]["options"].index(field_value)
        build_config["api_endpoint"]["options"] = build_config["database_name"]["options_metadata"][index][
            "api_endpoints"
        ]
        build_config["api_endpoint"]["value"] = build_config["database_name"]["options_metadata"][index][
            "api_endpoints"
        ][0]

        # Get the org_id for the selected database
        org_id = build_config["database_name"]["options_metadata"][index]["org_id"]
        if not org_id:
            return build_config

        # Update the list of keyspaces based on the db info
        build_config["keyspace"]["options"] = build_config["database_name"]["options_metadata"][index]["keyspaces"]
        build_config["keyspace"]["value"] = (
            build_config["keyspace"]["options"] and build_config["keyspace"]["options"][0]
            if build_config["keyspace"]["value"] not in build_config["keyspace"]["options"]
            else build_config["keyspace"]["value"]
        )

        # Get the database id for the selected database
        db_id = self.get_database_id_static(api_endpoint=build_config["api_endpoint"]["value"])
        keyspace = self.get_keyspace()

        # Update the helper text for the embedding provider field
        template = build_config["collection_name"]["dialog_inputs"]["fields"]["data"]["node"]["template"]
        template["02_embedding_generation_provider"]["helper_text"] = (
            "To create collections with more embedding provider options, go to "
            f'<a class="underline" target="_blank" rel="noopener noreferrer" '
            f'href="https://astra.datastax.com/org/{org_id}/database/{db_id}/data-explorer?createCollection=1&namespace={keyspace}">'
            "your database in Astra DB</a>."
        )

        # Reset provider options
        build_config = self.reset_provider_options(build_config)

        return self.reset_collection_list(build_config)

    def _handle_collection_selection(self, build_config: dict, field_value: str) -> dict:
        """Handle collection selection and update embedding options."""
        build_config["autodetect_collection"]["value"] = True
        build_config = self.reset_collection_list(build_config)

        # Reset embedding model if collection selection changes
        if field_value and field_value not in build_config["collection_name"]["options"]:
            build_config["collection_name"]["options"].append(field_value)
            build_config["collection_name"]["options_metadata"].append(
                {
                    "records": 0,
                    "provider": None,
                    "icon": "vectorstores",
                    "model": None,
                }
            )
            build_config["autodetect_collection"]["value"] = False

        return build_config
