from pathlib import Path
from typing import Any

import pytest
from lfx.base.knowledge_bases.backends.base import BackendType, BaseVectorStoreBackend
from lfx.base.knowledge_bases.ingestion_sources.base import SourceType
from lfx.base.knowledge_bases.ingestion_sources.connector_base import KBConnectorSource


class _DummyBackend(BaseVectorStoreBackend):
    backend_type = BackendType.CHROMA

    def _build_vector_store(self):
        raise NotImplementedError


class _DummyConnector(KBConnectorSource):
    source_type = SourceType.S3
    display_name = "Dummy"

    async def list_items(self):
        if False:
            yield None

    async def fetch_content(self, item: Any):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_kb_backend_refuses_protected_process_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "server-master-key")
    backend = _DummyBackend(kb_name="kb", kb_path=tmp_path)

    assert await backend.resolve_secret("LANGFLOW_SECRET_KEY") is None


@pytest.mark.asyncio
async def test_kb_connector_refuses_protected_process_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "server-master-key")
    connector = _DummyConnector(user_id=None, source_config={})

    assert await connector.resolve_secret("LANGFLOW_SECRET_KEY") is None
