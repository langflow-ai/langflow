"""Unit tests for the Weaviate vector store component.

These exercise the langchain-community 0.4.2 migration: the component moved off
``langchain_community.vectorstores.Weaviate`` (v3 client) to the standalone
``langchain_weaviate.WeaviateVectorStore`` backed by the Weaviate v4 client. The
network boundary (the v4 ``connect_*`` helpers and the store class) is mocked so
the migration logic runs in CI without a live Weaviate instance.
"""

from unittest.mock import MagicMock

import pytest
from lfx.components.weaviate.weaviate import WeaviateVectorStoreComponent
from lfx.schema.data import Data


def test_initialization():
    component = WeaviateVectorStoreComponent()
    assert component.display_name == "Weaviate"
    assert component.icon == "Weaviate"
    # The class name / identifier must remain stable: it keys saved flows.
    assert component.name == "Weaviate"


def test_build_vector_store_requires_capitalized_index():
    component = WeaviateVectorStoreComponent(url="http://localhost:8080", index_name="lowercase")
    with pytest.raises(ValueError, match="capitalized"):
        component.build_vector_store()


def test_connect_client_custom(mocker):
    """A self-hosted URL routes to the v4 connect_to_custom with derived host/port."""
    mock_connect = mocker.patch("weaviate.connect_to_custom", return_value=MagicMock())
    component = WeaviateVectorStoreComponent(url="http://localhost:8080", index_name="Test")

    client = component._connect_client()

    mock_connect.assert_called_once()
    _, kwargs = mock_connect.call_args
    assert kwargs["http_host"] == "localhost"
    assert kwargs["http_port"] == 8080
    assert kwargs["http_secure"] is False
    assert kwargs["grpc_host"] == "localhost"
    assert kwargs["grpc_port"] == 50051
    assert kwargs["auth_credentials"] is None
    assert client is mock_connect.return_value


def test_connect_client_cloud(mocker):
    """A Weaviate Cloud URL routes to connect_to_weaviate_cloud (gRPC resolved internally)."""
    mock_cloud = mocker.patch("weaviate.connect_to_weaviate_cloud", return_value=MagicMock())
    mock_auth = mocker.patch("lfx.components.weaviate.weaviate.AuthApiKey", return_value="AUTH")
    component = WeaviateVectorStoreComponent(
        url="https://my-cluster.weaviate.network",
        index_name="Test",
        api_key="test-key",  # pragma: allowlist secret
    )

    client = component._connect_client()

    mock_cloud.assert_called_once_with(cluster_url="https://my-cluster.weaviate.network", auth_credentials="AUTH")
    mock_auth.assert_called_once_with("test-key")
    assert client is mock_cloud.return_value


def test_connect_client_wraps_errors(mocker):
    mocker.patch("weaviate.connect_to_custom", side_effect=RuntimeError("boom"))
    component = WeaviateVectorStoreComponent(url="http://localhost:8080", index_name="Test")

    with pytest.raises(ValueError, match="Failed to connect to Weaviate"):
        component._connect_client()


def test_build_vector_store_without_documents(mocker):
    mock_client = MagicMock()
    mocker.patch.object(WeaviateVectorStoreComponent, "_connect_client", return_value=mock_client)
    mock_store_cls = mocker.patch("lfx.components.weaviate.weaviate.WeaviateVectorStore", return_value=MagicMock())
    fake_embedding = MagicMock()

    component = WeaviateVectorStoreComponent(url="http://localhost:8080", index_name="Test")
    component.embedding = fake_embedding

    store = component.build_vector_store()

    mock_store_cls.assert_called_once_with(
        client=mock_client,
        index_name="Test",
        text_key="text",
        embedding=fake_embedding,
    )
    mock_store_cls.from_documents.assert_not_called()
    assert store is mock_store_cls.return_value


def test_build_vector_store_with_documents_uses_from_documents(mocker):
    mock_client = MagicMock()
    mocker.patch.object(WeaviateVectorStoreComponent, "_connect_client", return_value=mock_client)
    mock_store_cls = mocker.patch("lfx.components.weaviate.weaviate.WeaviateVectorStore")
    fake_embedding = MagicMock()

    component = WeaviateVectorStoreComponent(url="http://localhost:8080", index_name="Test")
    component.embedding = fake_embedding
    component.ingest_data = [Data(data={"text": "hello"})]

    component.build_vector_store()

    mock_store_cls.from_documents.assert_called_once()
    _, kwargs = mock_store_cls.from_documents.call_args
    assert kwargs["client"] is mock_client
    assert kwargs["index_name"] == "Test"
    assert kwargs["text_key"] == "text"
    assert kwargs["embedding"] is fake_embedding


def test_search_documents_empty_query_returns_empty(mocker):
    mocker.patch.object(WeaviateVectorStoreComponent, "build_vector_store", return_value=MagicMock())
    component = WeaviateVectorStoreComponent(url="http://localhost:8080", index_name="Test")
    component.search_query = ""

    assert component.search_documents() == []
