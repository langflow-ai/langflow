from urllib.parse import urlparse

import weaviate
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data

# Weaviate Cloud hostnames end with these suffixes. For those the v4 client
# resolves the gRPC endpoint internally, so we avoid guessing a gRPC host/port.
_WEAVIATE_CLOUD_SUFFIXES = (".weaviate.network", ".weaviate.cloud")
_DEFAULT_GRPC_PORT = 50051


class WeaviateVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Weaviate"
    description = "Weaviate Vector Store with search capabilities"
    name = "Weaviate"
    icon = "Weaviate"

    inputs = [
        StrInput(name="url", display_name="Weaviate URL", value="http://localhost:8080", required=True),
        SecretStrInput(name="api_key", display_name="API Key", required=False),
        StrInput(
            name="index_name",
            display_name="Index Name",
            required=True,
            info="Requires capitalized index name.",
        ),
        StrInput(name="text_key", display_name="Text Key", value="text", advanced=True),
        StrInput(
            name="grpc_host",
            display_name="gRPC Host",
            advanced=True,
            info="gRPC host for a self-hosted Weaviate instance. Defaults to the URL host. "
            "Ignored when connecting to Weaviate Cloud.",
        ),
        IntInput(
            name="grpc_port",
            display_name="gRPC Port",
            value=_DEFAULT_GRPC_PORT,
            advanced=True,
            info="gRPC port for a self-hosted Weaviate instance. Ignored when connecting to Weaviate Cloud.",
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        BoolInput(
            name="search_by_text",
            display_name="Search By Text",
            advanced=True,
            info="Retained for backward compatibility. The Weaviate v4 client selects keyword vs. vector "
            "search automatically based on whether an embedding is provided.",
        ),
    ]

    def _connect_client(self) -> weaviate.WeaviateClient:
        """Connect to Weaviate using the v4 client API."""
        auth = AuthApiKey(self.api_key) if self.api_key else None
        parsed = urlparse(self.url)
        host = parsed.hostname or "localhost"
        http_secure = parsed.scheme == "https"
        http_port = parsed.port or (443 if http_secure else 8080)

        try:
            if http_secure and host.endswith(_WEAVIATE_CLOUD_SUFFIXES):
                return weaviate.connect_to_weaviate_cloud(cluster_url=self.url, auth_credentials=auth)
            return weaviate.connect_to_custom(
                http_host=host,
                http_port=http_port,
                http_secure=http_secure,
                grpc_host=self.grpc_host or host,
                grpc_port=self.grpc_port or _DEFAULT_GRPC_PORT,
                grpc_secure=http_secure,
                auth_credentials=auth,
            )
        except Exception as e:
            msg = f"Failed to connect to Weaviate at {self.url}: {e}"
            raise ValueError(msg) from e

    @check_cached_vector_store
    def build_vector_store(self) -> WeaviateVectorStore:
        if self.index_name != self.index_name.capitalize():
            msg = f"Weaviate requires the index name to be capitalized. Use: {self.index_name.capitalize()}"
            raise ValueError(msg)

        client = self._connect_client()

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents and self.embedding:
            return WeaviateVectorStore.from_documents(
                documents,
                embedding=self.embedding,
                client=client,
                index_name=self.index_name,
                text_key=self.text_key,
            )

        return WeaviateVectorStore(
            client=client,
            index_name=self.index_name,
            text_key=self.text_key,
            embedding=self.embedding,
        )

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        return []
