"""A2A Agent component — expose a Langflow flow as an Agent-to-Agent endpoint.

Bridges the Solis-style requirement: MCP Composer connects to an A2A agent as
a tool, with synchronous calls. This component publishes the current flow (or
a referenced flow) at a stable A2A URL and emits a handle that
``MCPComposerComponent`` can consume to wire the A2A agent into Composer's tool
graph.

See ``docs/docs/Agents/mcp-composer-component.mdx`` for how the handles
compose; A2A protocol details are out of scope here.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data

_DEFAULT_TIMEOUT_S = 60


def _a2a_base_url() -> str:
    return os.environ.get("LANGFLOW_A2A_BASE_URL", "/api/v1/a2a").rstrip("/")


class A2AAgentComponent(Component):
    display_name: str = "A2A Agent"
    description: str = (
        "Expose a flow as an A2A (Agent-to-Agent) endpoint. Returns a URL and "
        "handle that MCP Composer can consume as a tool with synchronous calls."
    )
    documentation: str = "https://docs.langflow.org/mcp-composer-component"
    icon = "Users"
    name = "A2AAgent"

    inputs = [
        MessageTextInput(
            name="flow_id",
            display_name="Flow ID",
            info="Flow to expose as an A2A agent. Defaults to the current flow.",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="agent_name",
            display_name="Agent Name",
            info="Public name MCP Composer will see when listing tools.",
            required=True,
        ),
        MessageTextInput(
            name="agent_description",
            display_name="Agent Description",
            info="Description shown to consuming agents. Should describe what the agent does.",
            required=True,
        ),
        BoolInput(
            name="synchronous",
            display_name="Synchronous Calls",
            value=True,
            info="If True, A2A calls block until the underlying flow completes (Solis requirement).",
        ),
        IntInput(
            name="timeout_s",
            display_name="Timeout (s)",
            value=_DEFAULT_TIMEOUT_S,
            advanced=True,
            range_spec={"min": 1, "max": 3600, "step": 1},
            info="Max wait for a synchronous call before the A2A endpoint returns an error.",
        ),
    ]

    outputs = [
        Output(display_name="A2A URL", name="a2a_url", method="resolve_a2a_url"),
        Output(display_name="A2A Handle", name="a2a_handle", method="resolve_a2a_handle"),
    ]

    def _resolve_flow_id(self) -> str:
        explicit = getattr(self, "flow_id", None)
        if explicit:
            # Coerce-validate; raise if not a UUID so users see the error early.
            return str(UUID(str(explicit)))
        graph = getattr(self, "graph", None)
        flow_id = getattr(graph, "flow_id", None) if graph else None
        if flow_id is None:
            msg = "A2AAgentComponent requires a flow_id (no current flow on the graph)"
            raise ValueError(msg)
        return str(flow_id)

    async def resolve_a2a_url(self) -> Data:
        if not self.agent_name:
            msg = "agent_name is required"
            raise ValueError(msg)
        flow_id = self._resolve_flow_id()
        url = f"{_a2a_base_url()}/agents/{flow_id}"
        return Data(data={"a2a_url": url, "agent_name": str(self.agent_name)})

    async def resolve_a2a_handle(self) -> Data:
        if not self.agent_name or not self.agent_description:
            msg = "agent_name and agent_description are required"
            raise ValueError(msg)
        flow_id = self._resolve_flow_id()
        url = f"{_a2a_base_url()}/agents/{flow_id}"
        payload: dict[str, Any] = {
            "a2a_url": url,
            "agent_name": str(self.agent_name),
            "agent_description": str(self.agent_description),
            "synchronous": bool(self.synchronous),
            "timeout_s": int(self.timeout_s or _DEFAULT_TIMEOUT_S),
            "flow_id": flow_id,
        }
        logger.debug("A2AAgentComponent handle resolved: %s", payload)
        # TODO(a2a-runtime): register the flow with the A2A router so the URL
        # above actually resolves. The router itself lives outside this PR; the
        # component shape here is what MCPComposerComponent needs to consume.
        return Data(data=payload)
