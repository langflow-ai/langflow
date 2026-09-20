"""Unit tests for the shared helpers of the IBM Confluent bundle (``lfx-confluent``)."""

from __future__ import annotations

import base64

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_confluent.components.confluent import _common


def test_basic_auth_header_encodes_key_and_secret():
    header = _common.basic_auth_header("key", "secret")  # pragma: allowlist secret
    assert header.startswith("Basic ")
    assert base64.b64decode(header.split(" ", 1)[1]).decode() == "key:secret"


@pytest.mark.parametrize(("key", "secret"), [("", "s"), ("k", ""), ("", "")])
def test_basic_auth_header_requires_both_parts(key, secret):
    with pytest.raises(ValueError, match="API key and the API secret"):
        _common.basic_auth_header(key, secret)


def test_context_engine_url_matches_confluent_pattern():
    url = _common.context_engine_url("us-east-1", "org-1", "env-abc", "lkc-xyz")
    assert url == (
        "https://mcp.us-east-1.aws.confluent.cloud/mcp/v1/context-engine/"
        "organizations/org-1/environments/env-abc/kafka-clusters/lkc-xyz"
    )


def test_tableflow_catalog_url_matches_confluent_pattern():
    url = _common.tableflow_catalog_url("us-west-2", "org-1", "env-abc")
    assert (
        url
        == "https://tableflow.us-west-2.aws.confluent.cloud/iceberg/catalog/organizations/org-1/environments/env-abc"
    )


@pytest.mark.parametrize("bad", ["", "   ", "env/../x", "env abc", "env?x=1", "-env"])
def test_require_token_rejects_non_tokens(bad):
    with pytest.raises(ValueError, match="Environment ID"):
        _common.require_token(bad, "Environment ID")


def test_parse_bootstrap_servers_defaults_port_and_splits():
    pairs = _common.parse_bootstrap_servers("a.example.com, b.example.com:9093 ,")
    assert pairs == [("a.example.com", 9092), ("b.example.com", 9093)]


@pytest.mark.parametrize("bad", ["", "host:notaport", "host:70000"])
def test_parse_bootstrap_servers_rejects_invalid(bad):
    with pytest.raises(ValueError, match=r"Bootstrap|port"):
        _common.parse_bootstrap_servers(bad)


def test_validate_bootstrap_servers_blocks_cloud_metadata_host():
    with pytest.raises(SSRFProtectionError):
        _common.validate_bootstrap_servers("169.254.169.254:9092")


def test_validate_bootstrap_servers_normalizes_allowed_hosts():
    normalized = _common.validate_bootstrap_servers("pkc-1.us-east-1.aws.confluent.cloud")
    assert normalized == "pkc-1.us-east-1.aws.confluent.cloud:9092"


def test_kafka_client_config_sasl_plain():
    cfg = _common.kafka_client_config("h:9092", "k", "s", extra={"acks": "all", "ignored": None})
    assert cfg == {
        "bootstrap.servers": "h:9092",
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": "k",
        "sasl.password": "s",  # pragma: allowlist secret
        "acks": "all",
    }


def test_kafka_client_config_unauthenticated_when_no_key():
    assert _common.kafka_client_config("h:9092", "", "") == {"bootstrap.servers": "h:9092"}


def test_kafka_client_config_rejects_half_credentials():
    with pytest.raises(ValueError, match="Both the Kafka API key"):
        _common.kafka_client_config("h:9092", "k", "")


@pytest.mark.parametrize(
    "protected",
    [
        {"bootstrap.servers": "169.254.169.254:9092"},
        {"metadata.broker.list": "10.0.0.5:9092"},
        {"security.protocol": "PLAINTEXT"},
        {"sasl.username": "someone-else"},
        {"SASL.Password": "swapped"},  # pragma: allowlist secret -- case-insensitive key match
        {"ssl.ca.location": "/tmp/attacker.pem"},
    ],
)
def test_kafka_client_config_rejects_protected_extra_keys(protected):
    """``extra`` must not re-point the client, downgrade TLS, or swap the credentials."""
    with pytest.raises(ValueError, match="cannot override"):
        _common.kafka_client_config("h:9092", "k", "s", extra=protected)


def test_kafka_client_config_extra_cannot_bypass_bootstrap_ssrf_validation():
    """The SSRF-gated bootstrap list survives an ``extra`` that points at a private host."""
    validated = _common.validate_bootstrap_servers("pkc-1.us-east-1.aws.confluent.cloud:9092")
    with pytest.raises(ValueError, match=r"bootstrap\.servers"):
        _common.kafka_client_config(validated, "k", "s", extra={"bootstrap.servers": "10.0.0.5:9092"})


def test_ensure_url_allowed_blocks_private_ip():
    with pytest.raises(SSRFProtectionError):
        _common.ensure_url_allowed("https://10.0.0.5/mcp")
