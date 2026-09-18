"""SSRF (CWE-918) guards on tenant-controlled KB backend URLs.

The OpenSearch cluster URL and the Chroma Cloud ``cloud_host``/``cloud_port``
are tenant-controlled (a per-user Langflow variable and the request body's
``backend_config`` respectively), so the backends validate them against the
connector SSRF policy before dialing. The behavioural regression guards live
in ``src/backend/tests/unit/base/knowledge_bases/``; this file mirrors the
minimal slices of those paths so the lfx coverage upload — the only report
codecov measures ``src/lfx`` from — sees the new lines exercised.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.knowledge_bases.backends import ChromaCloudBackend, OpenSearchBackend
from lfx.utils.ssrf_protection import SSRFProtectionError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def ssrf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the SSRF knobs so the tests don't depend on ambient settings."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", raising=False)


def _opensearch_backend(tmp_path: Path, url: str) -> OpenSearchBackend:
    backend = OpenSearchBackend(
        kb_name="kb_ssrf",
        kb_path=tmp_path,
        backend_config={"index_name": "test_index"},
    )
    # resolve_secret is called for url, then username, then password.
    backend.resolve_secret = AsyncMock(side_effect=[url, None, None])
    return backend


@pytest.mark.usefixtures("ssrf_env")
async def test_opensearch_resolve_secrets_blocks_cloud_metadata_url(tmp_path: Path) -> None:
    backend = _opensearch_backend(tmp_path, "http://169.254.169.254/latest/meta-data/")
    with pytest.raises(SSRFProtectionError, match="blocked"):
        await backend._resolve_secrets()


@pytest.mark.usefixtures("ssrf_env")
async def test_opensearch_test_connection_reports_ssrf_block(tmp_path: Path) -> None:
    # The blocked URL must surface as a failed test-connection result with an
    # accurate type — never as a dialed connection.
    backend = _opensearch_backend(tmp_path, "http://169.254.169.254:80")
    result = await backend.test_connection()
    assert result.ok is False
    assert result.details["type"] == "SSRFProtectionError"
    assert "blocked" in result.message


def _chroma_cloud_backend(tmp_path: Path, cfg: dict) -> ChromaCloudBackend:
    backend = ChromaCloudBackend(
        kb_name="cloud_kb",
        kb_path=tmp_path / "cloud_kb",
        backend_config=cfg,
    )
    backend._resolved_api_key = "k"
    return backend


@pytest.mark.usefixtures("ssrf_env")
def test_chroma_cloud_client_rejects_metadata_host(tmp_path: Path) -> None:
    # Tenant-controlled cloud_host must not reach the cloud-metadata address;
    # the SSRF policy fires before chromadb.CloudClient is built.
    backend = _chroma_cloud_backend(tmp_path, {"mode": "cloud", "cloud_host": "169.254.169.254"})
    with (
        patch("chromadb.CloudClient") as mock_cloud,
        pytest.raises(SSRFProtectionError, match="blocked"),
    ):
        backend._get_cloud_client()
    mock_cloud.assert_not_called()


def test_chroma_cloud_client_passes_allowlisted_host_and_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The custom host goes through connector SSRF validation; allowlisting it
    # exercises the pass-through and the configured-port handling.
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "custom.host.example")
    backend = _chroma_cloud_backend(
        tmp_path,
        {"mode": "cloud", "cloud_host": "custom.host.example", "cloud_port": "8080"},
    )

    with patch("chromadb.CloudClient", return_value=MagicMock()) as mock_cloud:
        backend._get_cloud_client()

    _, kwargs = mock_cloud.call_args
    assert kwargs["cloud_host"] == "custom.host.example"
    assert kwargs["cloud_port"] == 8080
