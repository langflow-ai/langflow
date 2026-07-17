import structlog
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.helpers.data import docs_to_data
from lfx.io import HandleInput, IntInput, SecretStrInput, StrInput
from lfx.schema.data import Data

logger = structlog.get_logger(__name__)


def _patch_check_index_exists():
    """Patch langchain-aws check_index_exists to handle valkey-glide RequestError.

    langchain-aws's check_index_exists only catches KeyError/ValueError/RuntimeError,
    but valkey-glide raises glide_shared.exceptions.RequestError when an index doesn't
    exist. This patch catches that specific exception so _create_index_if_not_exist
    can proceed to create the index.

    This is a workaround until langchain-aws handles the GLIDE exception itself.
    """
    try:
        import langchain_aws.vectorstores.valkey.base as _valkey_base
    except (ImportError, AttributeError):
        return

    if getattr(_valkey_base, "patched_check_index_exists", False):
        return

    try:
        from glide_shared.exceptions import RequestError as GlideRequestError
    except ImportError:
        return

    _original_check = _valkey_base.check_index_exists

    def _patched_check(client, index_name):
        try:
            return _original_check(client, index_name)
        except GlideRequestError:
            logger.debug("Valkey index does not exist yet", index_name=index_name)
            return False

    _valkey_base.check_index_exists = _patched_check
    _valkey_base.patched_check_index_exists = True


class ValkeyVectorStoreComponent(LCVectorStoreComponent):
    """A custom component for implementing a Vector Store using Valkey."""

    display_name: str = "Valkey"
    description: str = "Implementation of Vector Store using Valkey"
    name = "Valkey"
    icon = "Valkey"

    inputs = [
        SecretStrInput(name="valkey_server_url", display_name="Valkey Server Connection String", required=True),
        StrInput(name="valkey_index_name", display_name="Valkey Index"),
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
    def build_vector_store(self):
        import json

        from langchain_aws.vectorstores import ValkeyVectorStore

        _patch_check_index_exists()

        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        # Filter out documents with empty page_content — embedding models
        # (e.g. Bedrock) reject zero-length input strings.
        valid_documents = []
        for doc in documents:
            content = getattr(doc, "page_content", None) or ""
            if content.strip():
                valid_documents.append(doc)
            elif doc.metadata:
                doc.page_content = json.dumps(doc.metadata, default=str)
                valid_documents.append(doc)
            else:
                logger.warning("Valkey: skipping document with no content and no metadata")
        documents = valid_documents

        if not documents:
            if not self.valkey_index_name:
                msg = "If no documents are provided, an index name must be provided."
                raise ValueError(msg)

            return ValkeyVectorStore.from_existing_index(
                embedding=self.embedding,
                valkey_url=self.valkey_server_url,
                index_name=self.valkey_index_name,
            )

        return ValkeyVectorStore.from_documents(
            documents=documents,
            embedding=self.embedding,
            valkey_url=self.valkey_server_url,
            index_name=self.valkey_index_name,
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
