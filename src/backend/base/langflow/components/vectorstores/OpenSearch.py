from typing import TYPE_CHECKING, List, Optional, Dict, Any, Tuple
from langchain.schema import Document
from langchain_community.vectorstores import OpenSearchVectorSearch
from loguru import logger
from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.io import BoolInput, DataInput, HandleInput, IntInput, StrInput, MultilineInput, DropdownInput, FloatInput, SecretStrInput
from langflow.schema import Data
import traceback

if TYPE_CHECKING:
    from langchain_community.vectorstores import OpenSearchVectorSearch


class OpenSearchVectorStoreComponent(LCVectorStoreComponent):
    """
    OpenSearch Vector Store with advanced, customizable search capabilities.
    """

    display_name: str = "OpenSearch"
    description: str = "OpenSearch Vector Store with advanced, customizable search capabilities."
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/opensearch"
    name = "OpenSearch"
    icon = "OpenSearch"

    inputs = [
        StrInput(
            name="opensearch_url",
            display_name="OpenSearch URL",
            value="https://localhost:9200",
            info="URL for OpenSearch cluster (e.g. https://192.168.1.1:9200).",
        ),
        StrInput(
            name="index_name",
            display_name="Index Name",
            value="langflow",
            info="The index name where the vectors will be stored in OpenSearch cluster.",
        ),
        MultilineInput(
            name="search_input",
            display_name="Search Input",
            info="Enter a search query. Leave empty to retrieve all documents.",
        ),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
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
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> OpenSearchVectorSearch:
        """
        Builds the OpenSearch Vector Store object.
        """
        try:
            from langchain_community.vectorstores import OpenSearchVectorSearch
        except ImportError as e:
            logger.error(f"Failed to import required modules: {str(e)}")
            raise ImportError("Please ensure opensearchpy and langchain_community are installed.") from e

        try:
            if self.ingest_data:
                # Convert Data objects to langchain Documents
                documents = []
                for data in self.ingest_data:
                    if isinstance(data, Data):
                        doc = data.to_lc_document()
                        documents.append(doc)
                    else:
                        error_message = f"Expected Data object, got {type(data)}"
                        logger.error(error_message)
                        raise ValueError(error_message)

                # Create OpenSearchVectorSearch instance using from_documents method
                try:
                    opensearch = OpenSearchVectorSearch.from_documents(
                        documents,
                        self.embedding,
                        opensearch_url=self.opensearch_url,
                        http_auth=(self.username, self.password),
                        use_ssl=self.use_ssl,
                        verify_certs=self.verify_certs,
                        ssl_assert_hostname=False,
                        ssl_show_warn=False,
                        index_name=self.index_name,
                    )
                    return opensearch
                except Exception as e:
                    logger.error(f"Failed to create OpenSearchVectorSearch instance: {str(e)}")
                    raise RuntimeError(
                        "Error creating OpenSearchVectorSearch instance. Check your connection and credentials."
                    ) from e
            else:
                # No ingest_data provided, connect to existing index
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
                    return opensearch
                except Exception as e:
                    logger.error(f"Failed to connect to OpenSearchVectorSearch instance: {str(e)}")
                    raise RuntimeError(
                        "Error connecting to OpenSearchVectorSearch instance. Check your connection and credentials."
                    ) from e
        except Exception as e:
            logger.error(
                f"Unexpected error in build_vector_store, checkout if the username and the password were correctly set: {str(e)}"
            )
            raise RuntimeError(
                "An unexpected error occurred while building the vector store, checkout if the username and the password were correctly set."
            ) from e

    def _add_documents_to_vector_store(self, vector_store: "OpenSearchVectorSearch") -> None:
        """
        Adds documents to the Vector Store.
        """
        if not self.ingest_data:
            self.status = ""
            return

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                error_message = "Vector Store Inputs must be Data objects."
                logger.error(error_message)
                raise ValueError(error_message)

        if documents and self.embedding is not None:
            logger.debug(f"Adding {len(documents)} documents to the Vector Store.")
            try:
                vector_store.add_documents(documents)
            except Exception as e:
                error_message = f"Error adding documents to Vector Store: {str(e)}"
                logger.error(error_message)
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise Exception(error_message)
        else:
            logger.debug("No documents to add to the Vector Store.")

    def search(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar documents in the vector store or retrieve all documents if no query is provided.
        """
        try:
            vector_store = self.build_vector_store()
            search_kwargs = {"k": self.number_of_results, "score_threshold": self.search_score_threshold}

            if query:
                search_type = self.search_type.lower()
                if search_type == "similarity":
                    results = vector_store.similarity_search_with_score(query, **search_kwargs)
                    # Handle results with scores
                    return [
                        {"page_content": doc.page_content, "metadata": doc.metadata, "score": score}
                        for doc, score in results
                    ]
                elif search_type == "mmr":
                    results = vector_store.max_marginal_relevance_search(query, **search_kwargs)
                    # Handle results without scores
                    return [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in results]
                else:
                    raise ValueError(f"Invalid search type: {self.search_type}")
            else:
                # Retrieve all documents when no query is provided
                results = self.get_all_documents(vector_store, **search_kwargs)
                return [
                    {"page_content": doc.page_content, "metadata": doc.metadata, "score": score}
                    for doc, score in results
                ]
        except Exception as e:
            error_message = f"Error during search: {str(e)}"
            logger.error(error_message)
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(error_message)

    def get_all_documents(self, vector_store: OpenSearchVectorSearch, **kwargs) -> List[Tuple[Document, float]]:
        """
        Retrieve all documents from the vector store.
        """
        try:
            client = vector_store.client
            index_name = vector_store.index_name

            query = {"query": {"match_all": {}}, "size": kwargs.get("k", self.number_of_results)}

            response = client.search(index=index_name, body=query)

            results = []
            for hit in response["hits"]["hits"]:
                doc = Document(page_content=hit["_source"].get("text", ""), metadata=hit["_source"].get("metadata", {}))
                score = hit["_score"]
                results.append((doc, score))

            return results
        except Exception as e:
            error_message = f"Error retrieving all documents: {str(e)}"
            logger.error(error_message)
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(error_message)

    def search_documents(self) -> List[Data]:
        """
        Search for documents in the vector store based on the search input.
        If no search input is provided, retrieve all documents.
        """
        try:
            results = self.search(self.search_input)
            retrieved_data = [
                Data(filename=result["metadata"].get("file_path", ""), text=result["page_content"])
                for result in results
            ]
            self.status = retrieved_data
            return retrieved_data
        except Exception as e:
            error_message = f"Error during document search: {str(e)}"
            logger.error(error_message)
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(error_message)

    def get_retriever_kwargs(self):
        """
        Get the keyword arguments for the retriever.
        """
        return {
            "search_type": self.search_type.lower(),
            "search_kwargs": {"k": self.number_of_results, "score_threshold": self.search_score_threshold},
        }
