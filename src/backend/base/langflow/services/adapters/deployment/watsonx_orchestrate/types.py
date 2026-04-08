"""Dataclasses for the Watsonx Orchestrate adapter.

`WxOClient` eagerly creates SDK clients (`AgentClient`, `ToolClient`,
`ConnectionsClient`, and `BaseWXOClient`) at construction time to
guarantee thread safety when accessed from ``asyncio.to_thread`` workers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient
from ibm_watsonx_orchestrate_clients.common.base_client import BaseWXOClient, ClientAPIException
from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient, GetConnectionResponse
from ibm_watsonx_orchestrate_clients.tools.tool_client import ToolClient

from langflow.services.adapters.deployment.watsonx_orchestrate.local_dev import (
    is_wxo_local_instance_url,
    wxo_local_api_root_override,
    wxo_local_gateway_origin,
    wxo_local_use_default_api_v1_layout,
)

if TYPE_CHECKING:
    from ibm_cloud_sdk_core.authenticators import Authenticator

_logger = logging.getLogger(__name__)


def _wxo_de_pick_application_record(raw: Any, app_id: str) -> dict[str, Any] | None:
    """Normalize Developer Edition GET /connections/applications responses to a single record dict."""
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        rows = [x for x in raw if isinstance(x, dict)]
    elif isinstance(raw, dict):
        apps = raw.get("applications")
        rows = [x for x in apps if isinstance(x, dict)] if isinstance(apps, list) else [raw]
    for item in rows:
        aid = item.get("app_id") or item.get("appid")
        if aid != app_id:
            continue
        cid = item.get("connection_id") or item.get("connectionId") or item.get("id")
        if cid is None:
            cid = app_id
        normalized: dict[str, Any] = {
            "connection_id": str(cid),
            "app_id": str(app_id),
            "tenant_id": item.get("tenant_id"),
            "resource": item.get("resource"),
        }
        return normalized
    return None


def _normalize_wxo_model_catalog_items(items: list[Any]) -> list[dict[str, Any]]:
    """Map list entries to ``{"model_name": ...}`` for Langflow deployment LLM parsing."""
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            out.append({"model_name": item})
            continue
        if not isinstance(item, dict):
            continue
        if item.get("model_name") is not None:
            out.append({"model_name": str(item["model_name"])})
            continue
        mid = (
            item.get("id")
            or item.get("name")
            or item.get("modelId")
            or item.get("model_id")
        )
        if mid is not None:
            out.append({"model_name": str(mid)})
    return out


def _normalize_wxo_models_catalog_from_resources(resources: list[Any]) -> list[dict[str, Any]]:
    """Developer Edition ``GET /api/v1/models/list`` returns ``{"resources": [{id, label, ...}]}``."""
    return _normalize_wxo_model_catalog_items(resources)


def _wxo_nested_model_resources_list(payload: dict[str, Any]) -> list[Any] | None:
    """Resolve ``resources`` arrays possibly nested under ``data`` / ``result`` / similar."""
    direct = payload.get("resources")
    if isinstance(direct, list):
        return direct
    for wrap_key in ("data", "result", "payload", "response"):
        inner = payload.get(wrap_key)
        if isinstance(inner, dict):
            found = _wxo_nested_model_resources_list(inner)
            if found is not None:
                return found
    return None


def _normalize_wxo_models_catalog_response(raw: Any) -> Any:
    """Normalize wxO model catalog JSON to a list of ``{model_name: ...}`` dicts."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return _normalize_wxo_model_catalog_items(raw)
    if isinstance(raw, dict):
        nested_resources = _wxo_nested_model_resources_list(raw)
        if nested_resources is not None:
            return _normalize_wxo_models_catalog_from_resources(nested_resources)
        for key in ("models", "items", "results", "records"):
            chunk = raw.get(key)
            if isinstance(chunk, list):
                return _normalize_wxo_model_catalog_items(chunk)
        data_val = raw.get("data")
        if isinstance(data_val, list):
            return _normalize_wxo_model_catalog_items(data_val)
        _logger.warning(
            "wxO model catalog JSON shape not recognized (keys=%s); list_llms may fall back on loopback",
            list(raw.keys()),
        )
    return raw


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
        is_local = is_wxo_local_instance_url(url)
        client_kw: dict[str, Any] = {"base_url": url, "authenticator": self.authenticator}
        if is_local:
            client_kw["is_local"] = True
        base = BaseWXOClient(**client_kw)
        tool = ToolClient(**client_kw)
        connections = ConnectionsClient(**client_kw)
        agent = AgentClient(**client_kw)
        api_root = wxo_local_api_root_override()
        if api_root:
            normalized_root = api_root.rstrip("/")
            for client in (base, tool, connections, agent):
                client.base_url = normalized_root
        elif is_local:
            # Developer Edition OpenAPI: tools + models under /api/v1; agents + runs under
            # /api/v1/orchestrate; connections under /api/v1/connections/... (not .../orchestrate/connections).
            origin = wxo_local_gateway_origin(url)
            tool.base_url = f"{origin}/api/v1"
            agent.base_url = f"{origin}/api/v1"
            connections.base_url = f"{origin}/api/v1"
            base.base_url = f"{origin}/api/v1/orchestrate"
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "connections", connections)
        object.__setattr__(self, "agent", agent)

    # -- SDK private-method wrappers ------------------------------------------
    # Centralise access to SDK-internal _get/_post so breakage from SDK
    # upgrades is confined to this single file.

    def get_connection_draft_for_validation(self, app_id: str) -> GetConnectionResponse | None:
        """Return connection application metadata for validate_connection.

        Developer Edition often returns a JSON array (or ``{"applications": [...]}``) from
        ``GET /connections/applications``, which breaks IBM ``ConnectionsClient.get`` /
        ``GetConnectionResponse.model_validate`` (expects a single object dict).
        """
        if not wxo_local_use_default_api_v1_layout(self.instance_url):
            return self.connections.get_draft_by_app_id(app_id=app_id)
        cc = self.connections
        param_variants = (
            {"app_id": app_id},
            {"appid": app_id},
            {"app_id": app_id, "include_details": "true"},
        )
        last_not_found: ClientAPIException | None = None
        for params in param_variants:
            try:
                raw = cc._get("/connections/applications", params=params)  # noqa: SLF001
            except ClientAPIException as exc:
                if exc.response.status_code == HTTPStatus.NOT_FOUND:
                    last_not_found = exc
                    continue
                raise
            picked = _wxo_de_pick_application_record(raw, app_id)
            if picked is not None:
                return GetConnectionResponse.model_validate(picked)
        if last_not_found is not None:
            return None
        return None

    def get_agents_raw(self, params: dict[str, Any] | None = None) -> Any:
        # Loopback gateways (including when LANGFLOW_WXO_LOCAL_API_ROOT is set) must list agents
        # via AgentClient's Developer Edition path, not BaseWXOClient ``/agents`` under orchestrate.
        if is_wxo_local_instance_url(self.instance_url):
            return self.agent._get(self.agent.base_endpoint, params=params)  # noqa: SLF001
        return self.base._get("/agents", params=params)  # noqa: SLF001

    def get_models_raw(self, params: dict[str, Any] | None = None) -> Any:
        # Developer Edition catalog is GET /api/v1/models/list on the tool (api/v1) client.
        # Use it for every loopback/extra-local host URL, including when
        # ``LANGFLOW_WXO_LOCAL_API_ROOT`` is set — that flag only changes base_url but must
        # not switch to ``base._get("/models")`` (orchestrate layout), which breaks DE.
        if is_wxo_local_instance_url(self.instance_url):
            try:
                raw = self.tool._get("/models/list", params=params)  # noqa: SLF001
            except ClientAPIException as exc:
                if getattr(exc.response, "status_code", None) == HTTPStatus.NOT_FOUND:
                    raw = self.tool._get("/models", params=params)  # noqa: SLF001
                else:
                    raise
        else:
            raw = self.base._get("/models", params=params)  # noqa: SLF001
        return _normalize_wxo_models_catalog_response(raw)

    def post_model_raw(self, *, data: dict[str, Any]) -> Any:
        """Register a model with wxO (Developer Edition: ``POST /api/v1/models``).

        Use the same bearer token as Langflow's wxO provider. After a successful
        create, ``get_models_raw`` / ``GET .../models/list`` should include the new
        model for the deployment LLM picker.
        """
        if is_wxo_local_instance_url(self.instance_url):
            return self.tool._post("/models", data=data)  # noqa: SLF001
        return self.base._post("/models", data=data)  # noqa: SLF001

    def get_tools_raw(self, params: dict[str, Any] | None = None) -> Any:
        if is_wxo_local_instance_url(self.instance_url):
            return self.tool._get("/tools", params=params)  # noqa: SLF001
        return self.base._get("/tools", params=params)  # noqa: SLF001

    def post_run(self, *, data: dict[str, Any]) -> Any:
        return self.base._post("/runs", data=data)  # noqa: SLF001

    def get_run(self, run_id: str) -> Any:
        return self.base._get(f"/runs/{run_id}")  # noqa: SLF001

    def upload_tool_artifact(self, tool_id: str, *, files: dict[str, Any]) -> Any:
        if is_wxo_local_instance_url(self.instance_url):
            return self.tool._post(f"/tools/{tool_id}/upload", files=files)  # noqa: SLF001
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
