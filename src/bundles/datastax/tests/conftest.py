"""Shared fixtures for the DataStax bundle tests."""

import pytest

# Placeholder hosts used by the offline unit tests. They do not resolve, so the connector SSRF
# guard on the Astra/HCD endpoint boundary would reject them before the mocked client is reached.
# Allowlisting them keeps the guard switched ON (blocked-host coverage lives in
# ``test_astradb_connector_ssrf.py``) while letting endpoint-agnostic tests use fake URLs.
PLACEHOLDER_ENDPOINT_HOSTS = (
    "test.endpoint.com",
    "custom.endpoint.com",
    "x.apps.astra.datastax.com",
)


@pytest.fixture
def allow_placeholder_endpoints(monkeypatch):
    """Allowlist the fake API endpoints used by tests that are not about SSRF."""
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", ",".join(PLACEHOLDER_ENDPOINT_HOSTS))
