"""Saved-flow compatibility for the retired Chroma integration."""

from langchain_core.vectorstores import VectorStore

from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, IntInput, StrInput


class ChromaVectorStoreComponent(LCVectorStoreComponent):
    """Chroma Vector Store with search capabilities."""

    display_name: str = "Chroma DB"
    description: str = "Retired in 1.13. Migrate this store to a Knowledge Base before running this flow."
    legacy = True
    name = "Chroma"
    icon = "Chroma"

    inputs = [
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            value="langflow",
        ),
        StrInput(
            name="persist_directory",
            display_name="Persist Directory",
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="chroma_server_cors_allow_origins",
            display_name="Server CORS Allow Origins",
            advanced=True,
        ),
        StrInput(
            name="chroma_server_host",
            display_name="Server Host",
            advanced=True,
        ),
        IntInput(
            name="chroma_server_http_port",
            display_name="Server HTTP Port",
            advanced=True,
        ),
        IntInput(
            name="chroma_server_grpc_port",
            display_name="Server gRPC Port",
            advanced=True,
        ),
        BoolInput(
            name="chroma_server_ssl_enabled",
            display_name="Server SSL Enabled",
            advanced=True,
        ),
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

    @check_cached_vector_store
    def build_vector_store(self) -> VectorStore:
        """Reject execution of the retired component while retaining its saved identity."""
        raise ChromaMigrationRequiredError
