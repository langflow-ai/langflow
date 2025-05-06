import inspect
from abc import ABC

import graph_retriever.strategies as strategies_module
from langchain_graph_retriever import GraphRetriever

from langflow.base.vectorstores.model import LCVectorStoreComponent
from langflow.helpers import docs_to_data
from langflow.inputs import DropdownInput, HandleInput, MultilineInput, NestedDictInput, StrInput
from langflow.schema import Data


def traversal_strategies() -> list[str]:
    """Retrieves a list of class names from the strategies_module.

    This function uses the `inspect` module to get all the class members
    from the `strategies_module` and returns their names as a list of strings.

    Returns:
        list[str]: A list of strategy class names.
    """
    classes = inspect.getmembers(strategies_module, inspect.isclass)
    return [name for name, cls in classes if ABC not in cls.__bases__]


class GraphRAGComponent(LCVectorStoreComponent):
    """GraphRAGComponent is a component for performing Graph RAG traversal in a vector store.

    Attributes:
        display_name (str): The display name of the component.
        description (str): A brief description of the component.
        name (str): The name of the component.
        icon (str): The icon representing the component.
        inputs (list): A list of input configurations for the component.

    Methods:
        _build_search_args():
            Builds the arguments required for the search operation.
        search_documents() -> list[Data]:
            Searches for documents using the specified strategy, edge definition, and query.
        _edge_definition_from_input() -> tuple:
            Processes the edge definition input and returns it as a tuple.
    """

    display_name: str = "Graph RAG"
    description: str = "Graph RAG traversal for vector store."
    name = "Graph RAG"
    icon: str = "AstraDB"

    inputs = [
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            input_types=["Embeddings"],
            info="Specify the Embedding Model. Not required for Astra Vectorize collections.",
            required=False,
        ),
        HandleInput(
            name="vector_store",
            display_name="Vector Store Connection",
            input_types=["VectorStore"],
            info="Connection to Vector Store.",
        ),
        StrInput(
            name="edge_definition",
            display_name="Edge Definition",
            info="Edge definition for the graph traversal.",
        ),
        DropdownInput(
            name="strategy",
            display_name="Traversal Strategies",
            options=traversal_strategies(),
        ),
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
        NestedDictInput(
            name="graphrag_strategy_kwargs",
            display_name="Strategy Parameters",
            info=(
                "Optional dictionary of additional parameters for the retrieval strategy. "
                "Please see https://datastax.github.io/graph-rag/reference/graph_retriever/strategies/ for details."
            ),
            advanced=True,
        ),
    ]

    def search_documents(self) -> list[Data]:
        """Searches for documents using the graph retriever based on the selected strategy, edge definition, and query.

        Returns:
            list[Data]: A list of retrieved documents.

        Raises:
            AttributeError: If there is an issue with attribute access.
            TypeError: If there is a type mismatch.
            ValueError: If there is a value error.
        """
        additional_params = self.graphrag_strategy_kwargs or {}

        # Invoke the graph retriever based on the selected strategy, edge definition, and query
        strategy_class = getattr(strategies_module, self.strategy)
        retriever = GraphRetriever(
            store=self.vector_store,
            edges=[self._evaluate_edge_definition_input()],
            strategy=strategy_class(**additional_params),
        )

        return docs_to_data(retriever.invoke(self.search_query))

    def _edge_definition_from_input(self) -> tuple:
        """Generates the edge definition from the input data.

        Returns:
            tuple: A tuple representing the edge definition.
        """
        values = self.edge_definition.split(",")
        values = [value.strip() for value in values]

        return tuple(values)

    def _evaluate_edge_definition_input(self) -> tuple:
        from graph_retriever.edges.metadata import Id

        """Evaluates the edge definition, converting any function calls from strings.

        Args:
            edge_definition (tuple): The edge definition to evaluate.

        Returns:
            tuple: The evaluated edge definition.
        """
        evaluated_values = []
        for value in self._edge_definition_from_input():
            if value == "Id()":
                evaluated_values.append(Id())  # Evaluate Id() as a function call
            else:
                evaluated_values.append(value)
        return tuple(evaluated_values)
