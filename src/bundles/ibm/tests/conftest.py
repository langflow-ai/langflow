"""Shared fixtures for the ``lfx-ibm`` bundle tests.

The connector SSRF policy resolves host names through DNS, so the synthetic
watsonx.data host names used by the watsonx.data tests are allow-listed for
the duration of each test.  Literal private / metadata IPs are *not*
allow-listed, so the SSRF-rejection tests still exercise the real policy.
"""

from __future__ import annotations

import pytest

_TEST_HOSTS = (
    "presto.example.lakehouse.cloud.ibm.com",
    "my-instance.lakehouse.cloud.ibm.com",
    "other.example.com",
    "iam.cloud.ibm.com",
)


@pytest.fixture(autouse=True)
def _allowlist_test_hosts(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", ",".join(_TEST_HOSTS))
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
