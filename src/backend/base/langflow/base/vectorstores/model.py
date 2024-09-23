from abc import ABC, ABCMeta, abstractmethod
from functools import wraps
from typing import List, cast

from langchain_core.documents import Document
from loguru import logger

from langflow.custom import Component
from langflow.field_typing import Retriever, Text, VectorStore
from langflow.helpers.data import docs_to_data
from langflow.io import Output
from langflow.schema import Data


def check_cached_vector_store(f):
    """
    Decorator to check for cached vector stores, and returns them if they exist.
    """

    @wraps(f)
    def check_cached(self, *args, **kwargs):
        if self._cached_vector_store is not None:
            return self._cached_vector_store

        result = f(self, *args, **kwargs)
        self._cached_vector_store = result
        return result

    check_cached._is_cached_vector_store_checked = True
    return check_cached


class EnforceCacheDecoratorMeta(ABCMeta):
    """
    Enforces that abstract methods marked with @check_cached_vector_store are implemented with the decorator.
    """

    def __init__(cls, name, bases, dct):
        for name, value in dct.items():
            if hasattr(value, "__isabstractmethod__"):
                cls._check_method_decorator(name, cls)
        super().__init__(name, bases, dct)

    @staticmethod
    def _check_method_decorator(name, cls):
        method = getattr(cls, name)

        # Check if the method has been marked as decorated by `check_cached_vector_store`
        if not getattr(method, "_is_cached_vector_store_checked", False):
            raise TypeError(f"Concrete implementation of '{name}' must use '@check_cached_vector_store' decorator.")


class LCVectorStoreComponent(Component, ABC, metaclass=EnforceCacheDecoratorMeta):
    # Used to ensure a single vector store is built for each run of the flow
    _cached_vector_store: VectorStore | None = None

    trace_type = "retriever"
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
        Output(
            display_name="Vector Store",
            name="vector_store",
            method="cast_vector_store",
        ),
    ]

    def _validate_outputs(self):
        # At least these three outputs must be defined
        required_output_methods = [
            "build_base_retriever",
            "search_documents",
            "build_vector_store",
        ]
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

    def cast_vector_store(self) -> VectorStore:
        return cast(VectorStore, self.build_vector_store())

    def build_base_retriever(self) -> Retriever:  # type: ignore[type-var]
        """
        Builds the BaseRetriever object.
        """
        if self._cached_vector_store is not None:
            vector_store = self._cached_vector_store
        else:
            vector_store = self.build_vector_store()
            self._cached_vector_store = vector_store

        if hasattr(vector_store, "as_retriever"):
            retriever = vector_store.as_retriever(**self.get_retriever_kwargs())
            if self.status is None:
                self.status = "Retriever built successfully."
            return retriever
        else:
            raise ValueError(f"Vector Store {vector_store.__class__.__name__} does not have an as_retriever method.")

    def search_documents(self) -> List[Data]:
        """
        Search for documents in the vector store.
        """
        search_query: str = self.search_query
        if not search_query:
            self.status = ""
            return []

        if self._cached_vector_store is not None:
            vector_store = self._cached_vector_store
        else:
            vector_store = self.build_vector_store()
            self._cached_vector_store = vector_store

        logger.debug(f"Search input: {search_query}")
        logger.debug(f"Search type: {self.search_type}")
        logger.debug(f"Number of results: {self.number_of_results}")

        search_results = self.search_with_vector_store(
            search_query, self.search_type, vector_store, k=self.number_of_results
        )
        self.status = search_results
        return search_results

    def get_retriever_kwargs(self):
        """
        Get the retriever kwargs. Implementations can override this method to provide custom retriever kwargs.
        """
        return {}

    @abstractmethod
    @check_cached_vector_store
    def build_vector_store(self) -> VectorStore:
        """
        Builds the Vector Store object.
        """
        raise NotImplementedError("build_vector_store method must be implemented.")
