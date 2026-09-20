"""Confluent Real-Time Context Engine as an Agent toolset."""

from __future__ import annotations

from typing import Any

from lfx.base.mcp.preset import MCPPresetComponent, preset_control_inputs
from lfx.io import SecretStrInput, StrInput
from lfx_confluent.components.confluent._common import (
    DEFAULT_CLOUD,
    DEFAULT_REGION,
    basic_auth_header,
    context_engine_url,
    ensure_url_allowed,
)

# Tool names documented by Confluent for the Real-Time Context Engine MCP server.
CONTEXT_ENGINE_TOOLS = ["list_topics", "get_metadata", "query_data"]


class ConfluentContextEngineComponent(MCPPresetComponent):
    """Serve fresh, governed Kafka topic data to an Agent through the Real-Time Context Engine.

    Confluent's Real-Time Context Engine materializes schema'd Kafka topics into
    a low-latency serving layer and exposes it as an MCP server with three
    tools -- ``list_topics``, ``get_metadata`` and ``query_data`` (key lookups,
    filters, ranges and compound predicates).  This component templates the
    regional endpoint from your Confluent Cloud IDs, authenticates with a
    Confluent Cloud API key, and hands the tools to an Agent.
    """

    display_name = "Confluent Real-Time Context Engine"
    description = (
        "Give an Agent live, governed context from Kafka topics through Confluent's "
        "Real-Time Context Engine (MCP): list topics, inspect schemas, and query the latest data."
    )
    documentation: str = "https://docs.langflow.org/bundles-confluent"
    icon = "Confluent"
    name = "ConfluentContextEngine"
    metadata = {"keywords": ["confluent", "kafka", "context engine", "mcp", "real-time", "streaming", "ibm"]}

    inputs = [
        StrInput(
            name="region",
            display_name="Cloud Region",
            info="Confluent Cloud region of the Kafka cluster (for example us-east-1). AWS regions only today.",
            value=DEFAULT_REGION,
            required=True,
        ),
        StrInput(
            name="organization_id",
            display_name="Organization ID",
            info="Confluent Cloud organization ID (from Organization settings).",
            required=True,
        ),
        StrInput(
            name="environment_id",
            display_name="Environment ID",
            info="Confluent Cloud environment ID (for example env-abc123).",
            required=True,
        ),
        StrInput(
            name="kafka_cluster_id",
            display_name="Kafka Cluster ID",
            info="Kafka cluster ID (for example lkc-abc123) whose topics have the Context Engine enabled.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Confluent Cloud Global API key with read access to the cluster and Schema Registry.",
            required=True,
        ),
        SecretStrInput(
            name="api_secret",
            display_name="API Secret",
            info="Secret paired with the API key.",
            required=True,
        ),
        StrInput(
            name="endpoint_override",
            display_name="Endpoint Override",
            info=(
                "Full MCP endpoint URL. Leave empty to build it from the region and IDs; set it when "
                "Confluent publishes a different host for your cloud provider or region."
            ),
            advanced=True,
        ),
        StrInput(
            name="cloud",
            display_name="Cloud Provider",
            info="Cloud provider segment of the endpoint host. The Context Engine is available on AWS today.",
            value=DEFAULT_CLOUD,
            advanced=True,
        ),
        *preset_control_inputs(
            CONTEXT_ENGINE_TOOLS,
            tool_info=(
                "Tool to run for the Response output. In Tool Mode all three tools are exposed to the "
                "Agent. Use the refresh button to re-read the tool list from the server."
            ),
        ),
    ]

    def endpoint_url(self) -> str:
        override = (getattr(self, "endpoint_override", "") or "").strip()
        if override:
            return ensure_url_allowed(override)
        url = context_engine_url(
            self.region,
            self.organization_id,
            self.environment_id,
            self.kafka_cluster_id,
            cloud=getattr(self, "cloud", DEFAULT_CLOUD) or DEFAULT_CLOUD,
        )
        return ensure_url_allowed(url)

    def _mcp_server_config(self) -> tuple[str, dict[str, Any]]:
        url = self.endpoint_url()
        headers = {"Authorization": basic_auth_header(self.api_key, self.api_secret)}
        server_name = f"confluent-context-engine-{(self.kafka_cluster_id or '').strip() or 'cluster'}"
        return server_name, {
            "url": url,
            "headers": headers,
            "mode": "Streamable_HTTP",
            "verify_ssl": bool(getattr(self, "verify_ssl", True)),
        }
