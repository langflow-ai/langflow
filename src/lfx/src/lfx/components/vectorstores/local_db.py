from copy import deepcopy
from pathlib import Path

from langchain_chroma import Chroma
from loguru import logger
from typing_extensions import override

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.utils import chroma_collection_to_data
from lfx.inputs.inputs import MultilineInput
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, TabInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output


class LocalDBComponent(LCVectorStoreComponent):
    """Chroma Vector Store with search capabilities."""

    display_name: str = "Local DB"
    description: str = "Local Vector Store with search capabilities"
    name = "LocalDB"
    icon = "database"

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Ingest", "Retrieve"],
            info="Select the operation mode",
            value="Ingest",
            real_time_refresh=True,
            show=True,
        ),
        MessageTextInput(
            name="collection_name",
            display_name="Collection Name",
            value="langflow",
            required=True,
        ),
        MessageTextInput(
            name="persist_directory",
            display_name="Persist Directory",
            info=(
                "Custom base directory to save the vector store. "
                "Collections will be stored under '{directory}/vector_stores/{collection_name}'. "
                "If not specified, it will use your system's cache folder."
            ),
            advanced=True,
        ),
        DropdownInput(
            name="existing_collections",
            display_name="Existing Collections",
            options=[],  # Will be populated dynamically
            info="Select a previously created collection to search through its stored data.",
            show=False,
            combobox=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", required=True, input_types=["Embeddings"]),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            advanced=True,
            info="If false, will not add documents that are already in the Vector Store.",
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
            advanced=True,
        ),
        HandleInput(
            name="ingest_data",
            display_name="Ingest Data",
            input_types=["Data", "DataFrame"],
            is_list=True,
            info="Data to store. It will be embedded and indexed for semantic search.",
            show=True,
        ),
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
            info="Enter text to search for similar content in the selected collection.",
            show=False,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=10,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            advanced=True,
            info="Limit the number of records to compare when Allow Duplicates is False.",
        ),
    ]
    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="perform_search"),
    ]

    def get_vector_store_directory(self, base_dir: str | Path) -> Path:
        """Get the full directory path for a collection."""
        # Ensure base_dir is a Path object
        base_dir = Path(base_dir)
        # Create the full path: base_dir/vector_stores/collection_name
        full_path = base_dir / "vector_stores" / self.collection_name
        # Create the directory if it doesn't exist
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path

    def get_default_persist_dir(self) -> str:
        """Get the default persist directory from cache."""
        from lfx.services.cache.utils import CACHE_DIR

        return str(self.get_vector_store_directory(CACHE_DIR))

    def list_existing_collections(self) -> list[str]:
        """List existing vector store collections from the persist directory."""
        from lfx.services.cache.utils import CACHE_DIR

        # Get the base directory (either custom or cache)
        base_dir = Path(self.persist_directory) if self.persist_directory else Path(CACHE_DIR)
        # Get the vector_stores subdirectory
        vector_stores_dir = base_dir / "vector_stores"
        if not vector_stores_dir.exists():
            return []

        return [d.name for d in vector_stores_dir.iterdir() if d.is_dir()]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update the build configuration when the mode changes."""
        if field_name == "mode":
            # Hide all dynamic fields by default
            dynamic_fields = [
                "ingest_data",
                "search_query",
                "search_type",
                "number_of_results",
                "existing_collections",
                "collection_name",
                "embedding",
                "allow_duplicates",
                "limit",
            ]
            for field in dynamic_fields:
                if field in build_config:
                    build_config[field]["show"] = False

            # Show/hide fields based on selected mode
            if field_value == "Ingest":
                if "ingest_data" in build_config:
                    build_config["ingest_data"]["show"] = True
                if "collection_name" in build_config:
                    build_config["collection_name"]["show"] = True
                    build_config["collection_name"]["display_name"] = "Name Your Collection"
                if "persist" in build_config:
                    build_config["persist"]["show"] = True
                if "persist_directory" in build_config:
                    build_config["persist_directory"]["show"] = True
                if "embedding" in build_config:
                    build_config["embedding"]["show"] = True
                if "allow_duplicates" in build_config:
                    build_config["allow_duplicates"]["show"] = True
                if "limit" in build_config:
                    build_config["limit"]["show"] = True
            elif field_value == "Retrieve":
                if "persist" in build_config:
                    build_config["persist"]["show"] = False
                build_config["search_query"]["show"] = True
                build_config["search_type"]["show"] = True
                build_config["number_of_results"]["show"] = True
                build_config["embedding"]["show"] = True
                build_config["collection_name"]["show"] = False
                # Show existing collections dropdown and update its options
                if "existing_collections" in build_config:
                    build_config["existing_collections"]["show"] = True
                    build_config["existing_collections"]["options"] = self.list_existing_collections()
                # Hide collection_name in Retrieve mode since we use existing_collections
        elif field_name == "existing_collections":
            # Update collection_name when an existing collection is selected
            if "collection_name" in build_config:
                build_config["collection_name"]["value"] = field_value

        return build_config

    @override
    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        """Builds the Chroma object."""
        try:
            from langchain_chroma import Chroma
        except ImportError as e:
            msg = "Could not import Chroma integration package. Please install it with `pip install langchain-chroma`."
            raise ImportError(msg) from e
        # Chroma settings
        # chroma_settings = None
        if self.existing_collections:
            self.collection_name = self.existing_collections

        # Use user-provided directory or default cache directory
        if self.persist_directory:
            base_dir = self.resolve_path(self.persist_directory)
            persist_directory = str(self.get_vector_store_directory(base_dir))
            logger.debug(f"Using custom persist directory: {persist_directory}")
        else:
            persist_directory = self.get_default_persist_dir()
            logger.debug(f"Using default persist directory: {persist_directory}")

        chroma = Chroma(
            persist_directory=persist_directory,
            client=None,
            embedding_function=self.embedding,
            collection_name=self.collection_name,
        )

        self._add_documents_to_vector_store(chroma)
        self.status = chroma_collection_to_data(chroma.get(limit=self.limit))
        return chroma

    def _add_documents_to_vector_store(self, vector_store: "Chroma") -> None:
        """Adds documents to the Vector Store."""
        ingest_data: list | Data | DataFrame = self.ingest_data
        if not ingest_data:
            self.status = ""
            return

        # Convert DataFrame to Data if needed using parent's method
        ingest_data = self._prepare_ingest_data()

        stored_documents_without_id = []
        if self.allow_duplicates:
            stored_data = []
        else:
            stored_data = chroma_collection_to_data(vector_store.get(limit=self.limit))
            for value in deepcopy(stored_data):
                del value.id
                stored_documents_without_id.append(value)

        documents = []
        for _input in ingest_data or []:
            if isinstance(_input, Data):
                if _input not in stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        if documents and self.embedding is not None:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            vector_store.add_documents(documents)
        else:
            self.log("No documents to add to the Vector Store.")

    def perform_search(self) -> DataFrame:
        return DataFrame(self.search_documents())
