"""Dataclasses for the Watsonx Orchestrate adapter.

`WxOClient` lazily creates SDK clients (`AgentClient`, `ToolClient`,
`ConnectionsClient`, and `BaseWXOClient`) on first use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient
from ibm_watsonx_orchestrate_clients.common.base_client import BaseWXOClient
from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient
from ibm_watsonx_orchestrate_clients.tools.tool_client import ToolClient

if TYPE_CHECKING:
    from ibm_cloud_sdk_core.authenticators import Authenticator


@dataclass(slots=True)
class WxOClient:
    """Provider client facade with lazy SDK client initialization.

    The adapter accesses this object through stable attributes/properties:
    - `agent`, `tool`, `connections`: created only when first accessed
    - `base`: shared low-level client used by wrapper methods in this class
    """

    instance_url: str
    authenticator: Authenticator
    _base: BaseWXOClient | None = field(init=False, default=None, repr=False)
    _tool: ToolClient | None = field(init=False, default=None, repr=False)
    _connections: ConnectionsClient | None = field(init=False, default=None, repr=False)
    _agent: AgentClient | None = field(init=False, default=None, repr=False)

    @property
    def base(self) -> BaseWXOClient:
        if self._base is None:
            self._base = BaseWXOClient(base_url=self.instance_url, authenticator=self.authenticator)
        return self._base

    @property
    def tool(self) -> ToolClient:
        if self._tool is None:
            self._tool = ToolClient(base_url=self.instance_url, authenticator=self.authenticator)
        return self._tool

    @property
    def connections(self) -> ConnectionsClient:
        if self._connections is None:
            self._connections = ConnectionsClient(base_url=self.instance_url, authenticator=self.authenticator)
        return self._connections

    @property
    def agent(self) -> AgentClient:
        if self._agent is None:
            self._agent = AgentClient(base_url=self.instance_url, authenticator=self.authenticator)
        return self._agent

    # -- SDK private-method wrappers ------------------------------------------
    # Centralise access to SDK-internal _get/_post so breakage from SDK
    # upgrades is confined to this single file.

    def get_agents_raw(self, params: dict[str, Any] | None = None) -> Any:
        return self.base._get("/agents", params=params)  # noqa: SLF001

    def post_run(self, *, query_suffix: str = "", data: dict[str, Any]) -> Any:
        return self.base._post(f"/runs{query_suffix}", data=data)  # noqa: SLF001

    def get_run(self, run_id: str) -> Any:
        return self.base._get(f"/runs/{run_id}")  # noqa: SLF001

    def upload_tool_artifact(self, tool_id: str, *, files: dict[str, Any]) -> Any:
        return self.base._post(f"/tools/{tool_id}/upload", files=files)  # noqa: SLF001


@dataclass(slots=True)
class WxOCredentials:
    instance_url: str
    authenticator: Authenticator = field(repr=False)

    def __repr__(self) -> str:
        return (
            f"WxOCredentials(instance_url={self.instance_url!r}, authenticator={self.authenticator.__class__.__name__})"
        )
