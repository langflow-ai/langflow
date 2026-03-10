"""Dataclasses for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
    tool: ToolClient
    connections: ConnectionsClient
    agent: AgentClient
    _base: BaseWXOClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        from ibm_watsonx_orchestrate_clients.common.base_client import BaseWXOClient

        self._base = BaseWXOClient(base_url=self.instance_url, authenticator=self.authenticator)

    # -- SDK private-method wrappers ------------------------------------------
    # Centralise access to SDK-internal _get/_post so breakage from SDK
    # upgrades is confined to this single file.

    def get_agents_raw(self, params: dict[str, Any] | None = None) -> Any:
        return self._base._get("/agents", params=params)  # noqa: SLF001

    def post_run(self, *, query_suffix: str = "", data: dict[str, Any]) -> Any:
        return self._base._post(f"/runs{query_suffix}", data=data)  # noqa: SLF001

    def get_run(self, run_id: str) -> Any:
        return self._base._get(f"/runs/{run_id}")  # noqa: SLF001

    def upload_tool_artifact(self, tool_id: str, *, files: dict[str, Any]) -> Any:
        return self._base._post(f"/tools/{tool_id}/upload", files=files)  # noqa: SLF001


@dataclass(slots=True)
class WxOCredentials:
    instance_url: str
    api_key: str

    def __repr__(self) -> str:
        return f"WxOCredentials(instance_url={self.instance_url!r}, api_key='****')"
