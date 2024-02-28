from typing import List

from langchain_core.vectorstores import VectorStore

from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Record, docs_to_records


class LCVectorStoreComponent(CustomComponent):

    display_name: str = "LC Vector Store"
    description: str = "Search a LC Vector Store for similar documents."
    beta: bool = True

    def search_with_vector_store(
        self, input_value: Text, search_type: str, vector_store: VectorStore
    ) -> List[Record]:
        """
        Search for records in the vector store based on the input value and search type.

        Args:
            input_value (Text): The input value to search for.
            search_type (str): The type of search to perform.
            vector_store (VectorStore): The vector store to search in.

        Returns:
            List[Record]: A list of records matching the search criteria.

        Raises:
            ValueError: If invalid inputs are provided.
        """

        docs = []
        if input_value and isinstance(input_value, str):
            docs = vector_store.search(
                query=input_value, search_type=search_type.lower()
            )
        else:
            raise ValueError("Invalid inputs provided.")
        return docs_to_records(docs)
