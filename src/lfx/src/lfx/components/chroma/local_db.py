"""Saved-flow compatibility for the retired Local DB integration."""

from langchain_core.vectorstores import VectorStore

from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.inputs.inputs import MultilineInput
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, TabInput
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output


class LocalDBComponent(LCVectorStoreComponent):
    """Chroma Vector Store with search capabilities."""

    display_name: str = "Local DB"
    description: str = "Retired in 1.13. Migrate this store to a Knowledge Base before running this flow."
    name = "LocalDB"
    icon = "database"
    legacy = True

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
            input_types=["Data", "JSON", "DataFrame", "Table"],
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
        Output(display_name="Table", name="dataframe", method="perform_search"),
    ]

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
                    build_config["existing_collections"]["options"] = []
                # Hide collection_name in Retrieve mode since we use existing_collections
        elif field_name == "existing_collections":
            # Update collection_name when an existing collection is selected
            if "collection_name" in build_config:
                build_config["collection_name"]["value"] = field_value

        return build_config

    @check_cached_vector_store
    def build_vector_store(self) -> VectorStore:
        """Reject construction of the retired Local DB store and provide migration guidance."""
        raise ChromaMigrationRequiredError

    def perform_search(self) -> DataFrame:
        """Reject search through the retired Local DB component."""
        raise ChromaMigrationRequiredError
