"""Redis vector store must not dump ingested documents to the working directory."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_community")
pytest.importorskip("langchain_text_splitters")

from lfx.schema.data import Data
from lfx_bundles.redis.redis import RedisVectorStoreComponent


@pytest.fixture(autouse=True)
def _disable_connector_ssrf(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "false")


def test_build_vector_store_does_not_write_debug_documents_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    component = RedisVectorStoreComponent()
    component.redis_server_url = "redis://localhost:6379/0"
    component.redis_index_name = "test-index"
    component.schema = None
    component.ingest_data = [Data(text="secret document contents")]
    component.embedding = object()
    component.search_query = ""
    component.number_of_results = 4

    fake_vs = MagicMock(name="RedisVectorStore")
    with (
        patch("lfx_bundles.redis.redis.CharacterTextSplitter") as splitter_cls,
        patch("lfx_bundles.redis.redis.Redis.from_documents", return_value=fake_vs) as from_documents,
    ):
        splitter_cls.return_value.split_documents.side_effect = lambda docs: docs
        result = component.build_vector_store()

    assert result is fake_vs
    from_documents.assert_called_once()
    assert not (tmp_path / "docuemnts.txt").exists()
    assert not (tmp_path / "documents.txt").exists()
    assert list(tmp_path.iterdir()) == []


def test_connect_to_existing_index_does_not_write_debug_documents_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    component = RedisVectorStoreComponent()
    component.redis_server_url = "redis://localhost:6379/0"
    component.redis_index_name = "test-index"
    component.schema = "schema.yaml"
    component.ingest_data = []
    component.embedding = object()
    component.search_query = ""
    component.number_of_results = 4

    fake_vs = MagicMock(name="RedisVectorStore")
    with patch("lfx_bundles.redis.redis.Redis.from_existing_index", return_value=fake_vs) as from_existing_index:
        result = component.build_vector_store()

    assert result is fake_vs
    from_existing_index.assert_called_once()
    assert list(tmp_path.iterdir()) == []
