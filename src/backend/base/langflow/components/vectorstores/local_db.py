from copy import deepcopy
from pathlib import Path

from langchain_chroma import Chroma
from loguru import logger
from typing_extensions import override

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.base.vectorstores.utils import chroma_collection_to_data
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data, DataFrame


class LocalDBComponent(LCVectorStoreComponent):
    """Local Vector Store with search capabilities."""

    display_name: str = "Local DB"
    description: str = (
        "Local Vector Store for data storage and retrieval. "
        "Create local collections and search them using semantic similarity."
    )
    name = "LocalDB"
    icon = "database"
    ingest_data: list[Data] | DataFrame = []

    outputs = [
        Output(display_name="Search Results", name="dataframe", method="as_dataframe"),
    ]

    inputs = [
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["Ingest", "Retrieve"],
            info="Select the operation mode",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="collection_name",
            display_name="Name Your Collection",
            value="langflow",
            info="Create a named collection to store your data.",
            show=False,
        ),
        DropdownInput(
            name="existing_collections",
            display_name="Existing Collections",
            options=[],  # Will be populated dynamically
            info="Select a previously created collection to search through its stored data.",
            show=False,
        ),
        BoolInput(
            name="persist",
            display_name="Persist",
            info=(
                "Save the vector store to disk so it can be reused in future sessions. "
                "If enabled, data will be stored in the cache directory or a custom directory."
            ),
            advanced=True,
            value=True,
            show=False,
        ),
        MessageTextInput(
            name="persist_directory",
            display_name="Persist Directory",
            info=(
                "Custom directory to save the vector store. "
                "If not specified, it will use a default directory in your system's cache folder "
                "under 'langflow/vector_stores/your_collection_name'."
            ),
            advanced=True,
            show=False,
        ),
        HandleInput(
            name="ingest_data",
            display_name="Ingest Data",
            input_types=["Data", "DataFrame"],
            is_list=True,
            info="Data to store. It will be embbeded and indexed for semantic search.",
            show=False,
        ),
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
            info="Enter text to search for similar content in the selected collection.",
            show=False,
        ),
        BoolInput(
            name="should_cache_vector_store",
            display_name="Cache Vector Store",
            value=True,
            advanced=True,
            info=(
                "Cache the vector store in memory during the session. "
                "This improves performance when performing multiple operations on the same collection."
            ),
            show=False,
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            info=(
                "The embedding model to use for converting your data into vectors. "
                "Required for both storing and searching."
            ),
            show=False,
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            advanced=True,
            info=(
                "If false, data that is identical to existing entries will not be added to the vector store. "
                "This helps prevent duplicate content."
            ),
            show=False,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
            info=(
                "Similarity: Find the most similar entries. "
                "MMR (Maximal Marginal Relevance): Balance similarity with diversity in results."
            ),
            advanced=True,
            show=False,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Maximum number of similar entries to return in the search results.",
            advanced=True,
            value=10,
            show=False,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            advanced=True,
            info=(
                "Maximum number of entries to compare when checking for duplicates. "
                "Only applies when Allow Duplicates is False."
            ),
            show=False,
        ),
    ]

    def list_existing_collections(self) -> list[str]:
        """List existing vector store collections from the persist directory."""
        from langflow.services.cache.utils import CACHE_DIR

        vector_stores_dir = Path(CACHE_DIR) / "vector_stores"
        if not vector_stores_dir.exists():
            return []

        return [d.name for d in vector_stores_dir.iterdir() if d.is_dir()]

    def update_build_config(self, build_config, field_value, field_name=None):
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
                "persist",
                "persist_directory",
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
                build_config["search_query"]["show"] = True
                build_config["search_type"]["show"] = True
                build_config["number_of_results"]["show"] = True
                build_config["embedding"]["show"] = True
                # Show existing collections dropdown and update its options
                if "existing_collections" in build_config:
                    build_config["existing_collections"]["show"] = True
                    build_config["existing_collections"]["options"] = self.list_existing_collections()
                # Hide collection_name in Retrieve mode since we use existing_collections
                if "collection_name" in build_config:
                    build_config["collection_name"]["show"] = False
        elif field_name == "persist":
            # Show/hide persist_directory based on persist value
            if "persist_directory" in build_config:
                build_config["persist_directory"]["show"] = field_value
        elif field_name == "existing_collections":
            # Update collection_name when an existing collection is selected
            if "collection_name" in build_config:
                build_config["collection_name"]["value"] = field_value

        return build_config

    def get_default_persist_dir(self) -> str:
        """Get the default persist directory."""
        from langflow.services.cache.utils import CACHE_DIR

        # Use the existing vector_stores directory
        persist_dir = Path(CACHE_DIR) / "vector_stores" / self.collection_name
        persist_dir.mkdir(parents=True, exist_ok=True)

        return str(persist_dir)

    @override
    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        """Builds the vector store object."""
        try:
            from langchain_chroma import Chroma
        except ImportError as e:
            msg = "Could not import Chroma integration package. Please install it with `pip install langchain-chroma`."
            raise ImportError(msg) from e

        # Only use persist_directory if persist is True
        persist_directory = None
        if getattr(self, "persist", False):
            # Use user-provided directory or default
            if self.persist_directory:
                persist_directory = self.resolve_path(self.persist_directory)
            else:
                persist_directory = self.get_default_persist_dir()
                logger.debug(f"Using default persist directory: {persist_directory}")

        chroma = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embedding,
            collection_name=self.collection_name,
        )

        self._add_documents_to_vector_store(chroma)
        self.status = chroma_collection_to_data(chroma.get(limit=self.limit))

        return chroma

    def _add_documents_to_vector_store(self, vector_store: "Chroma") -> None:
        """Adds documents to the Vector Store."""
        if not self.ingest_data:
            self.status = ""
            return

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        stored_documents_without_id = []
        if self.allow_duplicates:
            stored_data = []
        else:
            stored_data = chroma_collection_to_data(vector_store.get(limit=self.limit))
            for value in deepcopy(stored_data):
                del value.id
                stored_documents_without_id.append(value)

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                if _input not in stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        if documents and self.embedding is not None:
            logger.debug(f"Adding {len(documents)} documents to the Vector Store.")
            vector_store.add_documents(documents)
        else:
            logger.debug("No documents to add to the Vector Store.")

    def search_documents(self) -> list[Data]:
        """Search for documents in the vector store."""
        vector_store = self.build_vector_store()

        if not self.search_query or not isinstance(self.search_query, str) or not self.search_query.strip():
            self.status = ""
            return []

        logger.debug(f"Search input: {self.search_query}")
        logger.debug(f"Search type: {self.search_type}")
        logger.debug(f"Number of results: {self.number_of_results}")

        if self.search_type == "Similarity":
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )
        else:  # MMR
            docs = vector_store.max_marginal_relevance_search(
                query=self.search_query,
                k=self.number_of_results,
            )

        data = docs_to_data(docs)
        self.status = data
        return data
