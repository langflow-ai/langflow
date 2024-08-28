import os
from typing import List

from astrapy.admin import parse_api_endpoint
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


def valid_nvidia_vectorize_region(api_endpoint: str) -> bool:
    """
    Check if the specified region is valid.

    Args:
    region (str): The region to check.

    Returns:
    bool: True if the region is contains hosted nvidia models, False otherwise.
    """
    parsed_endpoint = parse_api_endpoint(api_endpoint)
    if not parsed_endpoint:
        raise ValueError("Invalid ASTRA_DB_API_ENDPOINT")
    return parsed_endpoint.region in ["us-east-2"]


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
