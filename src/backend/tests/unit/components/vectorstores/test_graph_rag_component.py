import random

import pytest
from faker import Faker
from langchain_community.embeddings.fake import DeterministicFakeEmbedding
from langchain_core.documents import Document
from langchain_core.vectorstores.in_memory import InMemoryVectorStore
from langflow.components.vectorstores.graph_rag import GraphRAGComponent

from tests.base import ComponentTestBaseWithoutClient


class TestGraphRAGComponent(ComponentTestBaseWithoutClient):
    """Test suite for the GraphRAGComponent class, focusing on graph traversal and retrieval functionality.

    Fixtures:
        component_class: Returns the GraphRAGComponent class to be tested.
        animals: Provides a list of Document objects representing various animals with metadata.
        embedding: Provides a FakeEmbeddings instance with a specified size.
        vector_store: Initializes an InMemoryVectorStore with the provided animals and embedding.
        file_names_mapping: Returns an empty list since this component doesn't have version-specific files.
        default_kwargs: Returns an empty dictionary since this component doesn't have any default arguments.

    Test Cases:
        test_graphrag: Tests the search_documents method of the GraphRAGComponent class by setting attributes and
        verifying the number of results returned.
    """

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return GraphRAGComponent

    @pytest.fixture
    def animals(self, n: int = 20, match_prob: float = 0.3) -> list[Document]:
        """Animals dataset for testing.

        Generate a list of animal-related document objects with random metadata.

        Parameters:
            n (int): Number of documents to generate.
            match_prob (float): Probability of sharing metadata across documents.

        Returns:
            List[Document]: A list of generated Document objects.
        """
        # Initialize Faker for generating random text
        fake = Faker()
        random.seed(42)
        fake.seed_instance(42)

        # Define possible attributes for animals
        animal_types = ["mammal", "bird", "reptile", "insect"]
        habitats = ["savanna", "marine", "wetlands", "forest", "desert"]
        diets = ["carnivorous", "herbivorous", "omnivorous"]
        origins = ["north america", "south america", "africa", "asia", "australia"]

        shared_metadata = {}  # Common metadata that may be shared across documents

        def update_metadata(meta: dict) -> dict:
            """Modify metadata based on predefined conditions and probability."""
            if random.random() < match_prob:  # noqa: S311
                meta.update(shared_metadata)  # Apply shared metadata
            elif meta["type"] == "mammal":
                meta["habitat"] = random.choice(habitats)  # noqa: S311
            elif meta["type"] == "reptile":
                meta["diet"] = random.choice(diets)  # noqa: S311
            elif meta["type"] == "insect":
                meta["origin"] = random.choice(origins)  # noqa: S311
            return meta

        # Generate and return a list of documents
        return [
            Document(
                id=fake.uuid4(),
                page_content=fake.sentence(),
                metadata=update_metadata(
                    {
                        "type": random.choice(animal_types),  # noqa: S311
                        "number_of_legs": random.choice([0, 2, 4, 6, 8]),  # noqa: S311
                        "keywords": fake.words(random.randint(2, 5)),  # noqa: S311
                        # Add optional tags with 30% probability
                        **(
                            {
                                "tags": [
                                    {"a": random.randint(1, 10), "b": random.randint(1, 10)}  # noqa: S311
                                    for _ in range(random.randint(1, 2))  # noqa: S311
                                ]
                            }
                            if random.random() < 0.3  # noqa: S311
                            else {}
                        ),
                        # Add nested metadata with 20% probability
                        **({"nested": {"a": random.randint(1, 10)}} if random.random() < 0.2 else {}),  # noqa: S311
                    }
                ),
            )
            for _ in range(n)
        ]

    @pytest.fixture
    def embedding(self):
        return DeterministicFakeEmbedding(size=8)

    @pytest.fixture
    def vector_store(self, animals: list[Document], embedding: DeterministicFakeEmbedding) -> InMemoryVectorStore:
        """Return an empty list since this component doesn't have version-specific files."""
        store = InMemoryVectorStore(embedding=embedding)
        store.add_documents(animals)
        return store

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""

    @pytest.fixture
    def default_kwargs(self):
        """Return an empty dictionary since this component doesn't have any default arguments."""
        return {"k": 10, "start_k": 3, "max_depth": 2}

    def test_graphrag(
        self,
        component_class: GraphRAGComponent,
        embedding: DeterministicFakeEmbedding,
        vector_store: InMemoryVectorStore,
        default_kwargs,
    ):
        """Test GraphRAGComponent's document search functionality.

        This test verifies that the component correctly retrieves documents using the
        provided embedding model, vector store, and search query.

        Args:
            component_class (GraphRAGComponent): The component class to test.
            embedding (FakeEmbeddings): The embedding model for the component.
            vector_store (InMemoryVectorStore): The vector store used in retrieval.
            default_kwargs (dict): Default keyword arguments for the retrieval strategy.

        Returns:
            None: The test asserts that 10 search results are returned.
        """
        component = component_class()

        component.set_attributes(
            {
                "embedding_model": embedding,
                "vector_store": vector_store,
                "edge_definition": "type, type",
                "strategy": "Eager",
                "search_query": "information environment technology",
                "graphrag_strategy_kwargs": default_kwargs,
            }
        )

        results = component.search_documents()

        # Quantity of documents
        assert len(results) == 10

        # Ensures all the k-start_k documents returned via traversal have the same metadata as the
        # ones returned via the similarity search
        assert {doc.data["type"] for doc in results if doc.data["_depth"] == 0} == {
            doc.data["type"] for doc in results if doc.data["_depth"] >= 1
        }
