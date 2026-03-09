"""Dataclasses for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibm_cloud_sdk_core.authenticators import Authenticator
    from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient
    from ibm_watsonx_orchestrate_clients.common.base_client import BaseWXOClient
    from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ToolClient


@dataclass(slots=True)
class WxOClient:
    instance_url: str
    authenticator: Authenticator
    # Dedicated low-level HTTP client used for direct _get/_post calls so
    # endpoint intent (for example, /orchestrate/runs) is explicit and not
    # conflated with resource-specific clients such as AgentClient.
    base: BaseWXOClient
    tool: ToolClient
    connections: ConnectionsClient
    agent: AgentClient


@dataclass(slots=True)
class WxOCredentials:
    instance_url: str
    api_key: str

    def __repr__(self) -> str:
        return f"WxOCredentials(instance_url={self.instance_url!r}, api_key='****')"
