"""Dataclasses for the Watsonx Orchestrate adapter.

`WxOClient` eagerly creates SDK clients (`AgentClient`, `ToolClient`,
`ConnectionsClient`, and `BaseWXOClient`) at construction time to
guarantee thread safety when accessed from ``asyncio.to_thread`` workers.
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


@dataclass(frozen=True, slots=True)
class WxOClient:
    """Provider client facade with eager SDK client initialization.

    All sub-clients are constructed in ``__post_init__`` from ``instance_url``
    and ``authenticator`` so that they are guaranteed to share the same
    URL and authentication context. The dataclass is frozen to prevent
    post-construction mutation of credentials.
    """

    instance_url: str
    authenticator: Authenticator
    base: BaseWXOClient = field(init=False, repr=False)
    tool: ToolClient = field(init=False, repr=False)
    connections: ConnectionsClient = field(init=False, repr=False)
    agent: AgentClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        url = self.instance_url.rstrip("/")
        if not url:
            msg = "instance_url must be a non-empty string."
            raise ValueError(msg)
        # Use object.__setattr__ because the dataclass is frozen.
        object.__setattr__(self, "instance_url", url)
        object.__setattr__(self, "base", BaseWXOClient(base_url=url, authenticator=self.authenticator))
        object.__setattr__(self, "tool", ToolClient(base_url=url, authenticator=self.authenticator))
        object.__setattr__(self, "connections", ConnectionsClient(base_url=url, authenticator=self.authenticator))
        object.__setattr__(self, "agent", AgentClient(base_url=url, authenticator=self.authenticator))

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


@dataclass(frozen=True, slots=True)
class WxOCredentials:
    instance_url: str
    authenticator: Authenticator = field(repr=False)

    def __post_init__(self) -> None:
        if not self.instance_url or not self.instance_url.strip():
            msg = "instance_url must be a non-empty string."
            raise ValueError(msg)

    def __repr__(self) -> str:
        return (
            f"WxOCredentials(instance_url={self.instance_url!r}, authenticator={self.authenticator.__class__.__name__})"
        )
