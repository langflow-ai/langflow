from typing import List

from langchain_core.documents import Document

from langflow.custom import Component
from langflow.field_typing import Retriever, Text, VectorStore
from langflow.helpers.data import docs_to_data
from langflow.io import Output
from langflow.schema import Data


class LCVectorStoreComponent(Component):
    outputs = [
        Output(
            display_name="Retriever",
            name="base_retriever",
            method="build_base_retriever",
        ),
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
    ]

    def _validate_outputs(self):
        # At least these three outputs must be defined
        required_output_methods = ["build_vector_store", "build_base_retriever", "search_documents"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    def search_with_vector_store(
        self,
        input_value: Text,
        search_type: str,
        vector_store: VectorStore,
        k=10,
        **kwargs,
    ) -> List[Data]:
        """
        Search for data in the vector store based on the input value and search type.

        Args:
            input_value (Text): The input value to search for.
            search_type (str): The type of search to perform.
            vector_store (VectorStore): The vector store to search in.

        Returns:
            List[Data]: A list of data matching the search criteria.

        Raises:
            ValueError: If invalid inputs are provided.
        """

        docs: List[Document] = []
        if input_value and isinstance(input_value, str) and hasattr(vector_store, "search"):
            docs = vector_store.search(query=input_value, search_type=search_type.lower(), k=k, **kwargs)
        else:
            raise ValueError("Invalid inputs provided.")
        data = docs_to_data(docs)
        self.status = data
        return data

    def build_vector_store(self) -> VectorStore:
        """
        Builds the Vector Store object.
        """
        raise NotImplementedError("build_vector_store method must be implemented.")

    def build_base_retriever(self) -> Retriever:
        """
        Builds the BaseRetriever object.
        """
        vector_store = self.build_vector_store()
        if hasattr(vector_store, "as_retriever"):
            return vector_store.as_retriever()
        else:
            raise ValueError(f"Vector Store {vector_store.__class__.__name__} does not have an as_retriever method.")
