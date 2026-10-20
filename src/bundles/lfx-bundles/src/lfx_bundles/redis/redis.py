from pathlib import Path
from urllib.parse import urlparse

from langchain_community.vectorstores.redis import Redis
from langchain_text_splitters import CharacterTextSplitter
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_connector_loopback_allowed,
    is_connector_ssrf_validation_enabled,
    is_ssrf_protection_enabled,
    validate_connector_hostname_for_ssrf,
)


class RedisVectorStoreComponent(LCVectorStoreComponent):
    """A custom component for implementing a Vector Store using Redis."""

    display_name: str = "Redis"
    description: str = "Implementation of Vector Store using Redis"
    name = "Redis"
    icon = "Redis"

    inputs = [
        SecretStrInput(name="redis_server_url", display_name="Redis Server Connection String", required=True),
        StrInput(
            name="redis_index_name",
            display_name="Redis Index",
        ),
        StrInput(name="code", display_name="Code", advanced=True),
        StrInput(
            name="schema",
            display_name="Schema",
        ),
        *LCVectorStoreComponent.inputs,
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> Redis:
        if is_connector_ssrf_validation_enabled() and is_ssrf_protection_enabled():
            parsed_url = urlparse(self.redis_server_url)
            if parsed_url.scheme in {"redis+sentinel", "rediss+sentinel"}:
                # LangChain parses Sentinel URLs itself; redis-py's parse_url rejects them.
                # It defaults a missing Sentinel host to localhost.
                validate_connector_hostname_for_ssrf(parsed_url.hostname or "localhost")
            else:
                from redis.connection import parse_url

                connection = parse_url(self.redis_server_url)
                if host := connection.get("host"):
                    validate_connector_hostname_for_ssrf(host)
                elif "path" in connection and not is_connector_loopback_allowed():
                    msg = "Redis Unix sockets are blocked when connector loopback access is disabled."
                    raise SSRFProtectionError(msg)
                elif "path" not in connection:
                    # redis-py defaults a hostless redis:// URL to localhost.
                    validate_connector_hostname_for_ssrf("localhost")

        # Convert DataFrame to Data if needed using parent's method
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        Path("docuemnts.txt").write_text(str(documents), encoding="utf-8")

        if not documents:
            if self.schema is None:
                msg = "If no documents are provided, a schema must be provided."
                raise ValueError(msg)
            redis_vs = Redis.from_existing_index(
                embedding=self.embedding,
                index_name=self.redis_index_name,
                schema=self.schema,
                key_prefix=None,
                redis_url=self.redis_server_url,
            )
        else:
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            docs = text_splitter.split_documents(documents)
            redis_vs = Redis.from_documents(
                documents=docs,
                embedding=self.embedding,
                redis_url=self.redis_server_url,
                index_name=self.redis_index_name,
            )
        return redis_vs

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
