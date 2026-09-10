"""Shared fixtures for the ``lfx-confluent`` bundle tests.

The connector SSRF policy resolves host names through DNS, so the synthetic
Confluent host names used by these tests are allow-listed for the duration of
each test.  Literal private / metadata IPs are *not* allow-listed, so the
SSRF-rejection tests still exercise the real policy.
"""

from __future__ import annotations

import pytest

_TEST_HOSTS = (
    "pkc-1.us-east-1.aws.confluent.cloud",
    "mcp.us-east-1.aws.confluent.cloud",
    "mcp.example.com",
    "tableflow.us-east-1.aws.confluent.cloud",
    "tableflow.us-west-2.aws.confluent.cloud",
    "tableflow.example.com",
    "psrc-1.us-east-2.aws.confluent.cloud",
)


@pytest.fixture(autouse=True)
def _allowlist_test_hosts(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", ",".join(_TEST_HOSTS))
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
