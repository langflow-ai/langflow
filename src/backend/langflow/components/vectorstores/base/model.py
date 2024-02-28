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

        docs = []
        if input_value and isinstance(input_value, str):
            docs = vector_store.search(
                query=input_value, search_type=search_type.lower()
            )
        else:
            raise ValueError("Invalid inputs provided.")
        return docs_to_records(docs)
