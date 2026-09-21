"""SSRF regression tests for the OpenSearch and Chroma Cloud KB backends.

The connection target of both backends is fully tenant-controlled — OpenSearch
resolves its cluster URL from a tenant-written Langflow variable, Chroma Cloud
takes ``cloud_host`` / ``cloud_port`` straight from the request body — and the
test-connection route echoes the probe outcome back to the tenant. These tests
pin the connector SSRF policy at the sinks so a tenant cannot point the server
at cloud-metadata (169.254.169.254), RFC1918, or other blocked targets, while
legitimate public clusters (and allowlisted internal ones) keep working.
"""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.knowledge_bases.backends.chroma import ChromaCloudBackend
from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend
from lfx.utils import ssrf_protection

_METADATA_URL = "http://169.254.169.254/latest/meta-data/"


def _force_ssrf_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the SSRF toggles deterministic regardless of ambient settings."""
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", raising=False)
    monkeypatch.delenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", raising=False)


def _approve_kb_hosts_if_supported(monkeypatch: pytest.MonkeyPatch, hosts: str) -> None:
    """No-op unless the exclusive KB destination allow-list is present."""
    monkeypatch.setenv("LANGFLOW_KB_ALLOWED_HOSTS", hosts)


def _patch_dns(monkeypatch: pytest.MonkeyPatch, ips: list[str]) -> None:
    """Resolve every hostname to ``ips`` so no real DNS runs in tests."""
    monkeypatch.setattr(ssrf_protection, "resolve_hostname", lambda _host: list(ips))


def _opensearch_backend(monkeypatch: pytest.MonkeyPatch, url: str) -> OpenSearchBackend:
    """Build an OpenSearch backend whose ``OPENSEARCH_URL`` variable resolves to ``url``."""
    backend = OpenSearchBackend(kb_name="kb", backend_config={})

    async def fake_resolve_secret(variable_name: str) -> str | None:
        return {"OPENSEARCH_URL": url}.get(variable_name)

    monkeypatch.setattr(backend, "resolve_secret", fake_resolve_secret)
    return backend


def _chroma_cloud_backend(monkeypatch: pytest.MonkeyPatch, backend_config: dict) -> ChromaCloudBackend:
    """Build a Chroma Cloud backend with credentials pre-resolved."""
    backend = ChromaCloudBackend(kb_name="kb", backend_config=backend_config)

    async def fake_resolve_secret(_variable_name: str) -> str | None:
        return None

    async def fake_resolve_required_secret(_variable_name: str) -> str:
        return "test-api-key"  # pragma: allowlist secret

    monkeypatch.setattr(backend, "resolve_secret", fake_resolve_secret)
    monkeypatch.setattr(backend, "resolve_required_secret", fake_resolve_required_secret)
    return backend


# ---- OpenSearch sink -------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _METADATA_URL,
        "http://192.168.1.10:9200",
        "http://10.0.0.5:9200",
        "http://172.16.0.1:9200",
        "file:///etc/passwd",
        "gopher://169.254.169.254/",
    ],
)
async def test_opensearch_rejects_blocked_or_non_http_urls(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    _force_ssrf_on(monkeypatch)
    backend = _opensearch_backend(monkeypatch, url)
    with pytest.raises(ValueError, match="not allowed"):
        await backend._resolve_secrets()
    assert getattr(backend, "_resolved_url", None) is None


async def test_opensearch_rejects_hostname_resolving_to_metadata_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """A public-looking hostname that resolves to a blocked IP must not pass."""
    _force_ssrf_on(monkeypatch)
    _patch_dns(monkeypatch, ["169.254.169.254"])
    backend = _opensearch_backend(monkeypatch, "https://search.example.com:9200")
    with pytest.raises(ValueError, match="not allowed"):
        await backend._resolve_secrets()


async def test_opensearch_allows_public_cluster_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_ssrf_on(monkeypatch)
    _patch_dns(monkeypatch, ["93.184.216.34"])
    backend = _opensearch_backend(monkeypatch, "https://search.example.com:9200")
    await backend._resolve_secrets()
    assert backend._resolved_url == "https://search.example.com:9200"


async def test_opensearch_allows_literal_loopback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connectors allow a literal loopback host by default (local dev clusters)."""
    _force_ssrf_on(monkeypatch)
    backend = _opensearch_backend(monkeypatch, "http://localhost:9200")
    await backend._resolve_secrets()
    assert backend._resolved_url == "http://localhost:9200"


async def test_opensearch_blocks_loopback_when_connector_loopback_disallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_ssrf_on(monkeypatch)
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    backend = _opensearch_backend(monkeypatch, "http://127.0.0.1:9200")
    with pytest.raises(ValueError, match="not allowed"):
        await backend._resolve_secrets()


async def test_opensearch_respects_connector_validation_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can preserve legacy internal-cluster behavior explicitly."""
    _force_ssrf_on(monkeypatch)
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "false")
    backend = _opensearch_backend(monkeypatch, _METADATA_URL)
    await backend._resolve_secrets()
    assert backend._resolved_url == _METADATA_URL


async def test_opensearch_missing_url_still_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_ssrf_on(monkeypatch)
    backend = OpenSearchBackend(kb_name="kb", backend_config={})

    async def fake_resolve_secret(_variable_name: str) -> str | None:
        return None

    monkeypatch.setattr(backend, "resolve_secret", fake_resolve_secret)
    with pytest.raises(ValueError, match="OPENSEARCH_URL"):
        await backend._resolve_secrets()


# ---- Chroma Cloud sink -----------------------------------------------------


@pytest.mark.parametrize(
    "backend_config",
    [
        {"mode": "cloud", "cloud_host": "169.254.169.254", "cloud_port": 443},
        {"mode": "cloud", "cloud_host": "192.168.1.10", "cloud_port": 8000},
        {"mode": "cloud", "cloud_host": "10.0.0.5"},
        {"mode": "cloud", "cloud_host": "http://169.254.169.254"},
    ],
)
async def test_chroma_cloud_rejects_blocked_hosts(monkeypatch: pytest.MonkeyPatch, backend_config: dict) -> None:
    _force_ssrf_on(monkeypatch)
    backend = _chroma_cloud_backend(monkeypatch, backend_config)
    with pytest.raises(ValueError, match="not allowed"):
        await backend._resolve_secrets()


async def test_chroma_cloud_rejects_hostname_resolving_to_metadata_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_ssrf_on(monkeypatch)
    _patch_dns(monkeypatch, ["169.254.169.254"])
    backend = _chroma_cloud_backend(monkeypatch, {"mode": "cloud", "cloud_host": "chroma.example.com"})
    with pytest.raises(ValueError, match="not allowed"):
        await backend._resolve_secrets()


async def test_chroma_cloud_allows_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_ssrf_on(monkeypatch)
    _patch_dns(monkeypatch, ["93.184.216.34"])
    backend = _chroma_cloud_backend(monkeypatch, {"mode": "cloud", "cloud_host": "chroma.example.com"})
    await backend._resolve_secrets()
    assert backend._resolved_api_key == "test-api-key"  # pragma: allowlist secret


async def test_chroma_cloud_default_host_needs_no_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent ``cloud_host`` means the fixed chromadb default (api.trychroma.com)."""
    _force_ssrf_on(monkeypatch)
    backend = _chroma_cloud_backend(monkeypatch, {"mode": "cloud"})
    await backend._resolve_secrets()
    assert backend._resolved_api_key == "test-api-key"  # pragma: allowlist secret


async def test_chroma_cloud_respects_connector_validation_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_ssrf_on(monkeypatch)
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "false")
    backend = _chroma_cloud_backend(monkeypatch, {"mode": "cloud", "cloud_host": "169.254.169.254"})
    await backend._resolve_secrets()
    assert backend._resolved_api_key == "test-api-key"  # pragma: allowlist secret


# ---- structural guards -----------------------------------------------------


async def test_opensearch_ssrf_validation_runs_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The validator resolves DNS, so it must not run inline on the loop.

    ``_resolve_secrets`` is async, and a hostile or merely slow DNS record would
    otherwise stall every other task on the worker for the length of a lookup.

    The call count is part of the assertion: the validator briefly ran both in
    ``_resolve_secrets`` and in ``_validate_url``, resolving DNS twice per KB.
    """
    _force_ssrf_on(monkeypatch)
    backend = _opensearch_backend(monkeypatch, "https://opensearch.example.com:9200")

    offloaded: list[object] = []
    real_to_thread = asyncio.to_thread

    async def recording_to_thread(func, /, *args, **kwargs):
        offloaded.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with (
        patch("lfx.base.knowledge_bases.backends.opensearch.asyncio.to_thread", recording_to_thread),
        patch("lfx.base.knowledge_bases.backends.opensearch.validate_connector_url_for_ssrf") as mock_validate,
        contextlib.suppress(Exception),
    ):
        await backend._resolve_secrets()

    assert mock_validate in offloaded, "the SSRF validator resolved DNS on the event loop instead of in a worker thread"
    mock_validate.assert_called_once_with("https://opensearch.example.com:9200")


async def test_chroma_cloud_client_does_not_revalidate_on_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_get_cloud_client`` must not resolve DNS itself.

    ``vector_store`` builds lazily from a *sync* property, so a validator call in
    the client factory is a blocking lookup on the event loop for every ingest and
    search. ``_validate_cloud_target`` already covers every path via
    ``ensure_ready``.
    """
    _force_ssrf_on(monkeypatch)
    _approve_kb_hosts_if_supported(monkeypatch, "custom.host.example")
    backend = _chroma_cloud_backend(
        monkeypatch,
        {"mode": "cloud", "cloud_host": "custom.host.example", "cloud_port": "8080"},
    )
    backend._resolved_api_key = "test-api-key"  # pragma: allowlist secret

    with (
        patch("lfx.base.knowledge_bases.backends.chroma.validate_connector_url_for_ssrf") as mock_validate,
        patch("chromadb.CloudClient", return_value=MagicMock()) as mock_cloud,
    ):
        backend._get_cloud_client()

    mock_validate.assert_not_called()
    _, kwargs = mock_cloud.call_args
    assert kwargs["cloud_host"] == "custom.host.example"
    assert kwargs["cloud_port"] == 8080


async def test_chroma_cloud_resolve_secrets_blocks_metadata_host_before_any_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal happens in ensure_ready's hook, before chromadb.CloudClient exists."""
    _force_ssrf_on(monkeypatch)
    backend = _chroma_cloud_backend(monkeypatch, {"mode": "cloud", "cloud_host": "169.254.169.254"})
    with (
        patch("chromadb.CloudClient") as mock_cloud,
        pytest.raises(ssrf_protection.SSRFProtectionError, match="blocked"),
    ):
        await backend._resolve_secrets()
    mock_cloud.assert_not_called()
