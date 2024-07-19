import os
from typing import List

from langflow.field_typing import Embeddings


def check_env_vars(*vars):
    """
    Check if all specified environment variables are set.

    Args:
    *vars (str): The environment variables to check.

    Returns:
    bool: True if all environment variables are set, False otherwise.
    """
    return all(os.getenv(var) for var in vars)


class MockEmbeddings(Embeddings):
    def __init__(self):
        self.embedded_documents = None
        self.embedded_query = None

    @staticmethod
    def mock_embedding(text: str):
        return [len(text) / 2, len(text) / 5, len(text) / 10]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self.embedded_documents = texts
        return [self.mock_embedding(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        self.embedded_query = text
        return self.mock_embedding(text)
