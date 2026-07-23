"""Tests for the connector loopback carve-out in SSRF validation.

Connector / model-provider components routinely target a *local* service (Ollama and LM Studio
default to ``http://localhost:11434`` / ``http://localhost:1234``; local vector stores bind to
loopback). ``validate_connector_url_for_ssrf`` therefore allows a *literal* loopback host by
default, while still blocking cloud-metadata, RFC1918, and hostnames that merely resolve to
loopback. A multi-tenant deployer can set ``connector_ssrf_allow_loopback=false`` to block
loopback too. The API Request component / database / git validators are unaffected.
"""

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_connector_url_for_ssrf


@pytest.fixture(autouse=True)
def _ssrf_enabled(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/api/tags",
        "http://127.0.0.1:11434/api/tags",
        "http://127.0.0.5:1234/v1",
        "http://[::1]:11434/api/tags",
    ],
)
def test_connector_allows_literal_loopback_by_default(monkeypatch, url):
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "true")
    # Must not raise — local model servers / vector stores are reachable.
    validate_connector_url_for_ssrf(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://10.0.0.5:8000",  # RFC1918
        "http://192.168.1.10:11434",  # RFC1918
        "http://172.16.0.4:9000",  # RFC1918
    ],
)
def test_connector_still_blocks_metadata_and_private(monkeypatch, url):
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "true")
    with pytest.raises(SSRFProtectionError):
        validate_connector_url_for_ssrf(url)


@pytest.mark.parametrize("url", ["http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"])
def test_connector_blocks_loopback_when_opted_out(monkeypatch, url):
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "false")
    with pytest.raises(SSRFProtectionError):
        validate_connector_url_for_ssrf(url)
