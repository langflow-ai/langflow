"""MCP Composer component — surfaces a running MCP Composer instance in a flow.

Wraps the existing ``MCPComposerService`` (one process per project, OAuth-aware
proxy in front of Langflow's MCP endpoints). The component does not start a new
Composer process on every flow run; it ensures one is running for the project
and returns aggregated tools / resources / app references that downstream nodes
can consume.

See ``docs/docs/Agents/mcp-composer-component.mdx`` for the full spec.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DictInput, IntInput, MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema.data import Data

_DEFAULT_START_TIMEOUT_S = 80


class MCPComposerComponent(Component):
    display_name: str = "MCP Composer"
    description: str = (
        "Run MCP Composer for the current project and expose its aggregated "
        "tools, resources, and apps to downstream nodes."
    )
    documentation: str = "https://docs.langflow.org/mcp-composer-component"
    icon = "Server"
    name = "MCPComposer"

    inputs = [
        MessageTextInput(
            name="project_id",
            display_name="Project ID",
            info="Defaults to the current flow's project. One Composer process per project.",
            advanced=True,
            required=False,
        ),
        MessageTextInput(
            name="streamable_http_url",
            display_name="Upstream Streamable HTTP URL",
            info="Langflow MCP endpoint Composer proxies to. Defaults to the project's /streamable URL.",
            advanced=True,
            required=False,
        ),
        DictInput(
            name="auth_config",
            display_name="OAuth Config",
            info=(
                "OAuth credentials passed through to MCP Composer (oauth_host, oauth_port, "
                "oauth_server_url, oauth_callback_path, oauth_client_id, oauth_client_secret, "
                "oauth_auth_url, oauth_token_url, oauth_scopes)."
            ),
            is_list=True,
            required=False,
        ),
        MessageTextInput(
            name="app_filter",
            display_name="App Filter",
            info="Comma-separated list of Composer apps to expose. Empty = all apps.",
            advanced=True,
            required=False,
        ),
        IntInput(
            name="start_timeout_s",
            display_name="Start Timeout (s)",
            info="How long to wait for the Composer subprocess to bind its port.",
            value=_DEFAULT_START_TIMEOUT_S,
            advanced=True,
            range_spec={"min": 5, "max": 600, "step": 1},
        ),
        BoolInput(
            name="reuse_running",
            display_name="Reuse Running Composer",
            info="If True (default) and a Composer is already running for this project, reuse it.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Composer URL", name="composer_url", method="resolve_composer_url"),
        Output(display_name="Tools", name="tools", method="resolve_tools"),
        Output(display_name="Resources", name="resources", method="resolve_resources"),
        Output(display_name="App Handle", name="app_handle", method="resolve_app_handle"),
    ]

    def _resolve_project_id(self) -> UUID:
        raw = getattr(self, "project_id", None)
        if raw:
            return UUID(str(raw))
        graph = getattr(self, "graph", None)
        flow_project = getattr(graph, "project_id", None) if graph else None
        if flow_project:
            return UUID(str(flow_project))
        msg = "MCPComposerComponent requires a project_id (no current project on the graph)"
        raise ValueError(msg)

    async def _ensure_composer_running(self) -> str:
        from lfx.services.deps import get_service
        from lfx.services.schema import ServiceType

        service = get_service(ServiceType.MCP_COMPOSER_SERVICE)
        project_id = self._resolve_project_id()
        port = service.get_project_composer_port(project_id)
        if port is None or not self.reuse_running:
            await service.start_project_composer(
                project_id=project_id,
                streamable_http_url=self.streamable_http_url or "",
                auth_config=self.auth_config or {},
            )
            deadline = self.start_timeout_s or _DEFAULT_START_TIMEOUT_S
            elapsed = 0
            while elapsed < deadline:
                port = service.get_project_composer_port(project_id)
                if port is not None:
                    break
                await asyncio.sleep(1)
                elapsed += 1
            if port is None:
                last_err = service.get_last_error(project_id)
                msg = f"MCP Composer did not start within {deadline}s: {last_err or 'unknown error'}"
                raise RuntimeError(msg)
        return f"http://127.0.0.1:{port}"

    def _parse_app_filter(self) -> list[str]:
        raw = getattr(self, "app_filter", None)
        if not raw:
            return []
        return [item.strip() for item in str(raw).split(",") if item.strip()]

    async def resolve_composer_url(self) -> Data:
        url = await self._ensure_composer_running()
        return Data(data={"composer_url": url})

    async def resolve_tools(self) -> Data:
        """Aggregate tool descriptors across the selected Composer apps.

        The actual fetch is deferred until Composer exposes a stable ``/apps``
        endpoint. For now this returns a placeholder Data row with the
        composer URL so downstream nodes wire up correctly; the integration
        worker can replace this with a live HTTP call against Composer.
        """
        url = await self._ensure_composer_running()
        # TODO(mcp-composer): once Composer exposes /apps/<app>/tools, fetch and
        # filter by self._parse_app_filter() before returning.
        return Data(
            data={
                "composer_url": url,
                "app_filter": self._parse_app_filter(),
                "tools": [],
            }
        )

    async def resolve_resources(self) -> Data:
        url = await self._ensure_composer_running()
        # TODO(mcp-composer): same as resolve_tools but for /apps/<app>/resources.
        return Data(data={"composer_url": url, "resources": []})

    async def resolve_app_handle(self) -> Data:
        url = await self._ensure_composer_running()
        app_filter = self._parse_app_filter()
        # Opaque app handle — downstream components (e.g. A2AAgentComponent)
        # use the composer URL + app names to talk to Composer's app surface
        # directly without re-discovering tools/resources here.
        payload: dict[str, Any] = {
            "composer_url": url,
            "apps": app_filter,
            "project_id": str(self._resolve_project_id()),
        }
        logger.debug("MCPComposerComponent app_handle resolved: %s", payload)
        return Data(data=payload)
