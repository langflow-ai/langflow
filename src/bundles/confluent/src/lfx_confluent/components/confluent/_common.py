"""Shared helpers for the IBM Confluent bundle.

Small, dependency-free utilities used by every component in the bundle:
endpoint templating for the Confluent Cloud regional services, Basic-auth
header construction, Kafka client configuration for Confluent Cloud
(SASL_SSL / PLAIN with an API key + secret), and SSRF gating of every
tenant-supplied host through Langflow's connector policy.
"""

from __future__ import annotations

import base64
import re

from lfx.utils.ssrf_protection import validate_connector_url_for_ssrf

DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"
KAFKA_DEFAULT_PORT = 9092
MAX_PORT = 65535

# Confluent resource IDs (org / env / cluster / compute pool) and cloud
# region names are simple tokens.  Restricting them keeps user input from
# escaping the URL path segment it is interpolated into.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def require_token(value: str | None, label: str) -> str:
    """Return ``value`` stripped, or raise ``ValueError`` if it is empty or not a plain token."""
    text = (value or "").strip()
    if not text:
        msg = f"{label} is required."
        raise ValueError(msg)
    if not _TOKEN_RE.match(text):
        msg = f"{label} contains unsupported characters: {text!r}"
        raise ValueError(msg)
    return text


def basic_auth_header(api_key: str, api_secret: str) -> str:
    """Build the ``Authorization: Basic ...`` value Confluent Cloud expects for API-key auth."""
    key = (api_key or "").strip()
    secret = (api_secret or "").strip()
    if not key or not secret:
        msg = "Both the API key and the API secret are required."
        raise ValueError(msg)
    token = base64.b64encode(f"{key}:{secret}".encode()).decode("ascii")
    return f"Basic {token}"


def ensure_url_allowed(url: str) -> str:
    """SSRF-validate a tenant-supplied http(s) URL and return it stripped."""
    text = (url or "").strip()
    if not text:
        msg = "An endpoint URL is required."
        raise ValueError(msg)
    validate_connector_url_for_ssrf(text)
    return text


def context_engine_url(
    region: str,
    organization_id: str,
    environment_id: str,
    kafka_cluster_id: str,
    cloud: str = DEFAULT_CLOUD,
) -> str:
    """Return the Real-Time Context Engine MCP endpoint for a Kafka cluster.

    Pattern documented by Confluent::

        https://mcp.<REGION>.<CLOUD>.confluent.cloud/mcp/v1/context-engine/
            organizations/<ORG>/environments/<ENV>/kafka-clusters/<LKC>
    """
    region_ = require_token(region, "Region")
    cloud_ = require_token(cloud, "Cloud")
    org = require_token(organization_id, "Organization ID")
    env = require_token(environment_id, "Environment ID")
    lkc = require_token(kafka_cluster_id, "Kafka cluster ID")
    return (
        f"https://mcp.{region_}.{cloud_}.confluent.cloud/mcp/v1/context-engine/"
        f"organizations/{org}/environments/{env}/kafka-clusters/{lkc}"
    )


def tableflow_catalog_url(
    region: str,
    organization_id: str,
    environment_id: str,
    cloud: str = DEFAULT_CLOUD,
) -> str:
    """Return the Tableflow Iceberg REST catalog endpoint for an environment.

    Pattern documented by Confluent::

        https://tableflow.<REGION>.<CLOUD>.confluent.cloud/iceberg/catalog/
            organizations/<ORG>/environments/<ENV>
    """
    region_ = require_token(region, "Region")
    cloud_ = require_token(cloud, "Cloud")
    org = require_token(organization_id, "Organization ID")
    env = require_token(environment_id, "Environment ID")
    return (
        f"https://tableflow.{region_}.{cloud_}.confluent.cloud/iceberg/catalog/organizations/{org}/environments/{env}"
    )


# ``extra`` client settings are tenant-supplied (and reachable from Tool Mode), so they
# must not be able to re-point the client at another broker after the bootstrap list has
# been SSRF-gated, nor downgrade the transport or swap the SASL credentials.
PROTECTED_KAFKA_CONFIG_KEYS = frozenset(
    {
        "bootstrap.servers",
        "metadata.broker.list",
        "security.protocol",
    }
)
_PROTECTED_KAFKA_CONFIG_PREFIXES = ("sasl.", "ssl.")


def _is_protected_kafka_key(key: str) -> bool:
    """Return True for connection / transport / credential settings ``extra`` may not set."""
    name = (key or "").strip().lower()
    return name in PROTECTED_KAFKA_CONFIG_KEYS or name.startswith(_PROTECTED_KAFKA_CONFIG_PREFIXES)


def parse_bootstrap_servers(bootstrap_servers: str) -> list[tuple[str, int]]:
    """Split ``host:port,host:port`` into validated ``(host, port)`` pairs."""
    text = (bootstrap_servers or "").strip()
    if not text:
        msg = "Bootstrap servers are required (for example 'pkc-xxxxx.us-east-1.aws.confluent.cloud:9092')."
        raise ValueError(msg)
    pairs: list[tuple[str, int]] = []
    for raw in text.split(","):
        item = raw.strip()
        if not item:
            continue
        host, sep, port_text = item.rpartition(":")
        if not sep or not host:
            host, port = item, KAFKA_DEFAULT_PORT
        else:
            try:
                port = int(port_text)
            except ValueError as exc:
                msg = f"Invalid bootstrap server port in {item!r}."
                raise ValueError(msg) from exc
        if not (0 < port <= MAX_PORT):
            msg = f"Invalid bootstrap server port in {item!r}."
            raise ValueError(msg)
        pairs.append((host, port))
    if not pairs:
        msg = "Bootstrap servers are required."
        raise ValueError(msg)
    return pairs


def validate_bootstrap_servers(bootstrap_servers: str) -> str:
    """SSRF-gate every bootstrap host and return the normalized ``host:port`` list.

    Kafka bootstrap strings have no URL scheme, so each host is validated as
    an ``https://host:port`` URL -- the connector policy only looks at the host,
    which is what matters (cloud-metadata endpoints, RFC1918 literals, ...).
    """
    pairs = parse_bootstrap_servers(bootstrap_servers)
    for host, port in pairs:
        validate_connector_url_for_ssrf(f"https://{host}:{port}")
    return ",".join(f"{host}:{port}" for host, port in pairs)


def kafka_client_config(
    bootstrap_servers: str,
    api_key: str,
    api_secret: str,
    extra: dict | None = None,
) -> dict:
    """Return a ``confluent_kafka`` client config for Confluent Cloud (SASL_SSL / PLAIN).

    ``bootstrap_servers`` must already have passed :func:`validate_bootstrap_servers`.
    ``extra`` may tune the client (batching, timeouts, ...) but never the connection,
    transport or credentials -- see :data:`PROTECTED_KAFKA_CONFIG_KEYS`.
    """
    key = (api_key or "").strip()
    secret = (api_secret or "").strip()
    config: dict = {"bootstrap.servers": bootstrap_servers}
    if key or secret:
        if not key or not secret:
            msg = "Both the Kafka API key and the API secret are required for SASL authentication."
            raise ValueError(msg)
        config.update(
            {
                "security.protocol": "SASL_SSL",
                "sasl.mechanisms": "PLAIN",
                "sasl.username": key,
                "sasl.password": secret,
            }
        )
    if extra:
        protected = sorted(k for k in extra if _is_protected_kafka_key(k))
        if protected:
            msg = (
                "Extra Client Config cannot override the connection, transport or credential settings: "
                f"{', '.join(protected)}."
            )
            raise ValueError(msg)
        config.update({k: v for k, v in extra.items() if k and v is not None})
    return config
