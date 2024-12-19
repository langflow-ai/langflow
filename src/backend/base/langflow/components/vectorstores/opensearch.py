import json
from typing import Any

from langchain_community.vectorstores import OpenSearchVectorSearch

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data


class OpenSearchVectorStoreComponent(LCVectorStoreComponent):
    """OpenSearch Vector Store with advanced, customizable search capabilities."""

    display_name: str = "OpenSearch"
    description: str = "OpenSearch Vector Store with advanced, customizable search capabilities."
    name = "OpenSearch"
    icon = "OpenSearch"

    inputs = [
        StrInput(
            name="opensearch_url",
            display_name="OpenSearch URL",
            value="http://localhost:9200",
            info="URL for OpenSearch cluster (e.g. https://192.168.1.1:9200).",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info="The index name where the vectors will be stored in OpenSearch cluster.",
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["similarity", "similarity_score_threshold", "mmr"],
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
        StrInput(
            name="username",
            display_name="Username",
            value="admin",
            advanced=True,
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            value="admin",
            advanced=True,
        ),
        BoolInput(
            name="use_ssl",
            display_name="Use SSL",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="verify_certs",
            display_name="Verify Certificates",
            value=False,
            advanced=True,
        ),
        MultilineInput(
            name="hybrid_search_query",
            display_name="Hybrid Search Query",
            value="",
            advanced=True,
            info=(
                "Provide a custom hybrid search query in JSON format. This allows you to combine "
                "vector similarity and keyword matching."
            ),
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> OpenSearchVectorSearch:
        """Builds the OpenSearch Vector Store object."""
        try:
            from langchain_community.vectorstores import OpenSearchVectorSearch
        except ImportError as e:
            error_message = f"Failed to import required modules: {e}"
            self.log(error_message)
            raise ImportError(error_message) from e

        try:
            opensearch = OpenSearchVectorSearch(
                index_name=self.index_name,
                embedding_function=self.embedding,
                opensearch_url=self.opensearch_url,
                http_auth=(self.username, self.password),
                use_ssl=self.use_ssl,
                verify_certs=self.verify_certs,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
            )
        except Exception as e:
            error_message = f"Failed to create OpenSearchVectorSearch instance: {e}"
            self.log(error_message)
            raise RuntimeError(error_message) from e

        if self.ingest_data:
            self._add_documents_to_vector_store(opensearch)

        return opensearch

    def _add_documents_to_vector_store(self, vector_store: "OpenSearchVectorSearch") -> None:
        """Adds documents to the Vector Store."""
        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                error_message = f"Expected Data object, got {type(_input)}"
                self.log(error_message)
                raise TypeError(error_message)

        if documents and self.embedding is not None:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            try:
                vector_store.add_documents(documents)
            except Exception as e:
                error_message = f"Error adding documents to Vector Store: {e}"
                self.log(error_message)
                raise RuntimeError(error_message) from e
        else:
            self.log("No documents to add to the Vector Store.")

    def search(self, query: str | None = None) -> list[dict[str, Any]]:
        """Search for similar documents in the vector store or retrieve all documents if no query is provided."""
        try:
            vector_store = self.build_vector_store()

            query = query or ""

            if self.hybrid_search_query.strip():
                try:
                    hybrid_query = json.loads(self.hybrid_search_query)
                except json.JSONDecodeError as e:
                    error_message = f"Invalid hybrid search query JSON: {e}"
                    self.log(error_message)
                    raise ValueError(error_message) from e

                results = vector_store.client.search(index=self.index_name, body=hybrid_query)

                processed_results = []
                for hit in results.get("hits", {}).get("hits", []):
                    source = hit.get("_source", {})
                    text = source.get("text", "")
                    metadata = source.get("metadata", {})

                    if isinstance(text, dict):
                        text = text.get("text", "")

                    processed_results.append(
                        {
                            "page_content": text,
                            "metadata": metadata,
                        }
                    )
                return processed_results

            search_kwargs = {"k": self.number_of_results}
            search_type = self.search_type.lower()

            if search_type == "similarity":
                results = vector_store.similarity_search(query, **search_kwargs)
                return [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in results]
            if search_type == "similarity_score_threshold":
                search_kwargs["score_threshold"] = self.search_score_threshold
                results = vector_store.similarity_search_with_relevance_scores(query, **search_kwargs)
                return [
                    {
                        "page_content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": score,
                    }
                    for doc, score in results
                ]
            if search_type == "mmr":
                results = vector_store.max_marginal_relevance_search(query, **search_kwargs)
                return [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in results]

        except Exception as e:
            error_message = f"Error during search: {e}"
            self.log(error_message)
            raise RuntimeError(error_message) from e

        error_message = f"Error during search. Invalid search type: {self.search_type}"
        self.log(error_message)
        raise ValueError(error_message)

    def search_documents(self) -> list[Data]:
        """Search for documents in the vector store based on the search input.

        If no search input is provided, retrieve all documents.
        """
        try:
            query = self.search_query.strip() if self.search_query else None
            results = self.search(query)
            retrieved_data = [
                Data(
                    file_path=result["metadata"].get("file_path", ""),
                    text=result["page_content"],
                )
                for result in results
            ]
        except Exception as e:
            error_message = f"Error during document search: {e}"
            self.log(error_message)
            raise RuntimeError(error_message) from e

        self.status = retrieved_data
        return retrieved_data
