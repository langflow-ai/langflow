import os
import logging
from typing import Callable, Optional
import pytest
from pathlib import Path

from langchain_core.embeddings import Embeddings

from astrapy.core.db import AstraDB


def pytest_configure():
    data_path = Path(__file__).parent.absolute() / "data"

    # Uses a URL loader w/ OpenAIEmbeddings to embed into AstraDB.
    pytest.EMBEDDING_PATH = data_path / "embedding.json"
    # Uses OpenAIEmbeddings w/ AstraDBSearch to search for similar documents.
    pytest.VECTOR_STORE_SEARCH_PATH = data_path / "vector_search.json"

    for path in [
        pytest.EMBEDDING_PATH,
        pytest.VECTOR_STORE_SEARCH_PATH,
    ]:
        assert path.exists(), f"File {path} does not exist. Available files: {list(data_path.iterdir())}"


LOGGER = logging.getLogger(__name__)
DIR_PATH = os.path.dirname(os.path.abspath(__file__))


def _load_env() -> None:
    dotenv_path = os.path.join(DIR_PATH, os.pardir, ".env")
    if os.path.exists(dotenv_path):
        from dotenv import load_dotenv

        load_dotenv(dotenv_path)


_load_env()


def get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        LOGGER.warning(f"Missing environment variable: {name}")
        pytest.skip(f"Missing environment variable: {name}")

    return value


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown():
    LOGGER.info("Deleting existing collections")
    astra = AstraDB(
        token=get_env_var("ASTRA_DB_APPLICATION_TOKEN"),
        api_endpoint=get_env_var("ASTRA_DB_API_ENDPOINT"),
    )
    collections = astra.get_collections().get("status").get("collections")
    for c in collections:
        astra.delete_collection(c)

    yield

    LOGGER.info("Cleaning up collections")
    collections = astra.get_collections().get("status").get("collections")
    for c in collections:
        astra.delete_collection(c)


class MockEmbeddings(Embeddings):
    def __init__(self):
        self.embedded_documents = None
        self.embedded_query = None

    @staticmethod
    def mock_embedding(text: str):
        return [len(text) / 2, len(text) / 5, len(text) / 10]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_documents = texts
        return [self.mock_embedding(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embedded_query = text
        return self.mock_embedding(text)


@pytest.fixture
def embedding_flow() -> str:
    with open(pytest.EMBEDDING_PATH, "r") as f:
        return f.read()


@pytest.fixture
def vector_store_search_flow() -> str:
    with open(pytest.VECTOR_STORE_SEARCH_PATH, "r") as f:
        return f.read()


@pytest.fixture
def astradb_component() -> Callable:
    from langflow.components.vectorstores import AstraDBVectorStoreComponent

    def component_builder(
        collection: str,
        embedding: Optional[Embeddings] = None,
        inputs: Optional[list] = None,
    ):
        if embedding is None:
            embedding = MockEmbeddings()

        if inputs is None:
            inputs = []

        token = get_env_var("ASTRA_DB_APPLICATION_TOKEN")
        api_endpoint = get_env_var("ASTRA_DB_API_ENDPOINT")
        return AstraDBVectorStoreComponent().build(
            embedding=embedding,
            collection_name=collection,
            inputs=inputs,
            token=token,
            api_endpoint=api_endpoint,
        )

    return component_builder
