"""Opt-in helpers for Watsonx Orchestrate local development gateways.

Set ``LANGFLOW_WXO_LOCAL_DEV=true`` to allow ``http://`` provider URLs on loopback
hosts and to resolve auth from ``WXO_MCSP_LOCAL_TOKEN`` or a JWT supplied as the
provider ``api_key``.

Watsonx Orchestrate **Developer Edition** (``http://localhost:4321/docs``) exposes
platform APIs under ``/api/v1`` (e.g. tools, connections), model list under
``/api/v1/models/list`` (often ``{"resources": [{id, label, ...}]}``; Langflow maps
``id`` to ``model_name``), and orchestrate APIs under ``/api/v1/orchestrate`` (e.g.
agents, runs). Langflow adjusts SDK client roots for loopback URLs to match that
layout unless ``LANGFLOW_WXO_LOCAL_API_ROOT`` is set.

If the local gateway has no model catalog (or ``/models`` fails), deployment LLM
listing falls back to ``LANGFLOW_WXO_LOCAL_LLM_MODELS`` (comma-separated) in the
wxO adapter—see ``list_llms`` in ``service.py``.

If you **set** ``LANGFLOW_WXO_LOCAL_LLM_MODELS`` in the environment, those ids are
also **merged** into a successful catalog response on local URLs (deduped), so you
can surface model names wxO does not return. For real inference, wxO must be able
to reach the backend described in the model's ``provider_config``.

**Registering models on Developer Edition:** ``POST {origin}/api/v1/models`` (OpenAPI
in the gateway docs) creates a catalog entry—equivalent to your ``curl`` with JSON
body and the same JWT as Langflow. Programmatically, ``WxOClient.post_model_raw``
sends that request with the configured authenticator. Langflow's LLM list uses
``GET .../api/v1/models/list``; new models appear there once wxO persists them.

Flow tool artifacts use **unpinned** ``requirements.txt`` entries on loopback URLs
so wxO's TRM (``uv install`` on Linux) is not forced to match macOS-pinned versions
from the Langflow dev machine—see ``build_langflow_artifact_bytes`` in ``tools.py``.

Optional: ``LANGFLOW_WXO_LOCAL_API_ROOT`` — after SDK base-URL normalization, all
wxO HTTP clients use this exact root when your gateway uses a non-standard prefix.
The model catalog still uses ``GET …/models/list`` (not orchestrate ``/models``).

Optional: ``LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS`` — comma-separated extra hostnames
treated like loopback for URL layout, auth (JWT), and ``http://`` allowance
(e.g. ``host.docker.internal`` when Langflow runs in Docker but wxO is on the host).

Optional: ``LANGFLOW_WXO_DUMP_TOOL_ARTIFACTS`` — absolute or relative directory path.
Every wxO tool artifact upload (deploy or snapshot refresh) writes ``{tool_id}.zip``
there. Unzip to inspect the same ``*.json`` flow and ``requirements.txt`` sent to
wxO TRM — see ``upload_tool_artifact_bytes`` in ``tools.py``.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

_LOCAL_DEV_ENV = "LANGFLOW_WXO_LOCAL_DEV"
_BEARER_ENV = "WXO_MCSP_LOCAL_TOKEN"
_API_ROOT_ENV = "LANGFLOW_WXO_LOCAL_API_ROOT"
_EXTRA_INSTANCE_HOSTS_ENV = "LANGFLOW_WXO_LOCAL_INSTANCE_HOSTS"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def wxo_local_dev_enabled() -> bool:
    return os.getenv(_LOCAL_DEV_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def wxo_local_instance_hostnames() -> frozenset[str]:
    """Hostnames treated as local wxO (layout + JWT + http allowlist)."""
    raw = os.getenv(_EXTRA_INSTANCE_HOSTS_ENV, "").strip()
    if not raw:
        return _LOCAL_HOSTS
    extras = {h.strip().lower() for h in raw.split(",") if h.strip()}
    return frozenset(_LOCAL_HOSTS | extras)


def is_wxo_local_instance_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in wxo_local_instance_hostnames()


def wxo_local_gateway_origin(url: str) -> str:
    """Return ``scheme://host:port`` with no path (for building ``/api/v1`` prefixes)."""
    parsed = urlparse(url)
    if not parsed.hostname:
        return url.rstrip("/")
    scheme = (parsed.scheme or "http").lower()
    netloc = (parsed.netloc or "").lower()
    return urlunparse((scheme, netloc, "", "", "", "")).rstrip("/")


def wxo_local_use_default_api_v1_layout(instance_url: str) -> bool:
    """True when Langflow should apply Developer Edition ``/api/v1`` URL layout."""
    return is_wxo_local_instance_url(instance_url) and wxo_local_api_root_override() is None


def wxo_local_bearer_token_from_env() -> str | None:
    raw = os.getenv(_BEARER_ENV, "").strip()
    return raw or None


def wxo_local_api_root_override() -> str | None:
    raw = os.getenv(_API_ROOT_ENV, "").strip()
    return raw or None


def resolve_wxo_local_bearer_token(*, api_key: str) -> str | None:
    """Return bearer material for local wxO, or None if standard MCSP/IAM should be used."""
    if not wxo_local_dev_enabled():
        return None
    from_env = wxo_local_bearer_token_from_env()
    if from_env:
        return from_env
    key = (api_key or "").strip()
    if key.startswith("eyJ"):
        return key
    return None


class StaticJwtAuthenticator:
    """Satisfies ``ibm_watsonx_orchestrate_clients`` BaseAPIClient (uses ``token_manager.get_token``)."""

    __slots__ = ("token_manager",)

    def __init__(self, access_token: str) -> None:
        self.token_manager = _StaticTokenManager(access_token)


class _StaticTokenManager:
    __slots__ = ("_access_token",)

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def get_token(self) -> str:
        return self._access_token
