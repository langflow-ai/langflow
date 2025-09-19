from typing import Any

from elasticsearch import Elasticsearch
from langchain.schema import Document
from langchain_elasticsearch import ElasticsearchStore

from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data


class ElasticsearchVectorStoreComponent(LCVectorStoreComponent):
    """Elasticsearch Vector Store with with advanced, customizable search capabilities."""

    display_name: str = "Elasticsearch"
    description: str = "Elasticsearch Vector Store with with advanced, customizable search capabilities."
    name = "Elasticsearch"
    icon = "ElasticsearchStore"

    inputs = [
        StrInput(
            name="elasticsearch_url",
            display_name="Elasticsearch URL",
            value="http://localhost:9200",
            info="URL for self-managed Elasticsearch deployments (e.g., http://localhost:9200). "
            "Do not use with Elastic Cloud deployments, use Elastic Cloud ID instead.",
        ),
        SecretStrInput(
            name="cloud_id",
            display_name="Elastic Cloud ID",
            value="",
            info="Use this for Elastic Cloud deployments. Do not use together with 'Elasticsearch URL'.",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info="The index name where the vectors will be stored in Elasticsearch cluster.",
        ),
        *LCVectorStoreComponent.inputs,
        StrInput(
            name="username",
            display_name="Username",
            value="",
            advanced=False,
            info=(
                "Elasticsearch username (e.g., 'elastic'). "
                "Required for both local and Elastic Cloud setups unless API keys are used."
            ),
        ),
        SecretStrInput(
            name="password",
            display_name="Elasticsearch Password",
            value="",
            advanced=False,
            info=(
                "Elasticsearch password for the specified user. "
                "Required for both local and Elastic Cloud setups unless API keys are used."
            ),
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["similarity", "mmr"],
            value="similarity",
            advanced=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=4,
        ),
        FloatInput(
            name="search_score_threshold",
            display_name="Search Score Threshold",
            info="Minimum similarity score threshold for search results.",
            value=0.0,
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Elastic API Key",
            value="",
            advanced=True,
            info="API Key for Elastic Cloud authentication. If used, 'username' and 'password' are not required.",
        ),
        BoolInput(
            name="verify_certs",
            display_name="Verify SSL Certificates",
            value=True,
            advanced=True,
            info="Whether to verify SSL certificates when connecting to Elasticsearch.",
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> ElasticsearchStore:
        """Builds the Elasticsearch Vector Store object."""
        if self.cloud_id and self.elasticsearch_url:
            msg = (
                "Both 'cloud_id' and 'elasticsearch_url' provided. "
                "Please use only one based on your deployment (Cloud or Local)."
            )
            raise ValueError(msg)

        es_params = {
            "index_name": self.index_name,
            "embedding": self.embedding,
            "es_user": self.username or None,
            "es_password": self.password or None,
        }

        if self.cloud_id:
            es_params["es_cloud_id"] = self.cloud_id
        else:
            es_params["es_url"] = self.elasticsearch_url

        if self.api_key:
            es_params["api_key"] = self.api_key

        # Check if we need to verify SSL certificates
        if self.verify_certs is False:
            # Build client parameters for Elasticsearch constructor
            client_params: dict[str, Any] = {}
            client_params["verify_certs"] = False

            if self.cloud_id:
                client_params["cloud_id"] = self.cloud_id
            else:
                client_params["hosts"] = [self.elasticsearch_url]

            if self.api_key:
                client_params["api_key"] = self.api_key
            elif self.username and self.password:
                client_params["basic_auth"] = (self.username, self.password)

            es_client = Elasticsearch(**client_params)
            es_params["es_connection"] = es_client

        elasticsearch = ElasticsearchStore(**es_params)

        # If documents are provided, add them to the store
        if self.ingest_data:
            documents = self._prepare_documents()
            if documents:
                elasticsearch.add_documents(documents)

        return elasticsearch

    def _prepare_documents(self) -> list[Document]:
        """Prepares documents from the input data to add to the vector store."""
        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for data in self.ingest_data:
            if isinstance(data, Data):
                documents.append(data.to_lc_document())
            else:
                error_message = "Vector Store Inputs must be Data objects."
                self.log(error_message)
                raise TypeError(error_message)
        return documents

    def _add_documents_to_vector_store(self, vector_store: "ElasticsearchStore") -> None:
        """Adds documents to the Vector Store."""
        documents = self._prepare_documents()
        if documents and self.embedding:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            vector_store.add_documents(documents)
        else:
            self.log("No documents to add to the Vector Store.")

    def search(self, query: str | None = None) -> list[dict[str, Any]]:
        """Search for similar documents in the vector store or retrieve all documents if no query is provided."""
        vector_store = self.build_vector_store()
        search_kwargs = {
            "k": self.number_of_results,
            "score_threshold": self.search_score_threshold,
        }

        if query:
            search_type = self.search_type.lower()
            if search_type not in {"similarity", "mmr"}:
                msg = f"Invalid search type: {self.search_type}"
                self.log(msg)
                raise ValueError(msg)
            try:
                if search_type == "similarity":
                    results = vector_store.similarity_search_with_score(query, **search_kwargs)
                elif search_type == "mmr":
                    results = vector_store.max_marginal_relevance_search(query, **search_kwargs)
            except Exception as e:
                msg = (
                    "Error occurred while querying the Elasticsearch VectorStore,"
                    " there is no Data into the VectorStore."
                )
                self.log(msg)
                raise ValueError(msg) from e
            return [
                {"page_content": doc.page_content, "metadata": doc.metadata, "score": score} for doc, score in results
            ]
        results = self.get_all_documents(vector_store, **search_kwargs)
        return [{"page_content": doc.page_content, "metadata": doc.metadata, "score": score} for doc, score in results]

    def get_all_documents(self, vector_store: ElasticsearchStore, **kwargs) -> list[tuple[Document, float]]:
        """Retrieve all documents from the vector store."""
        client = vector_store.client
        index_name = self.index_name

        query = {
            "query": {"match_all": {}},
            "size": kwargs.get("k", self.number_of_results),
        }

        response = client.search(index=index_name, body=query)

        results = []
        for hit in response["hits"]["hits"]:
            doc = Document(
                page_content=hit["_source"].get("text", ""),
                metadata=hit["_source"].get("metadata", {}),
            )
            score = hit["_score"]
            results.append((doc, score))

        return results

    def search_documents(self) -> list[Data]:
        """Search for documents in the vector store based on the search input.

        If no search input is provided, retrieve all documents.
        """
        results = self.search(self.search_query)
        retrieved_data = [
            Data(
                text=result["page_content"],
                file_path=result["metadata"].get("file_path", ""),
            )
            for result in results
        ]
        self.status = retrieved_data
        return retrieved_data

    def get_retriever_kwargs(self):
        """Get the keyword arguments for the retriever."""
        return {
            "search_type": self.search_type.lower(),
            "search_kwargs": {
                "k": self.number_of_results,
                "score_threshold": self.search_score_threshold,
            },
        }
