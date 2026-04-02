"""Opt-in helpers for Watsonx Orchestrate local development gateways.

Set ``LANGFLOW_WXO_LOCAL_DEV=true`` to allow ``http://`` provider URLs on loopback
hosts and to resolve auth from ``WXO_MCSP_LOCAL_TOKEN`` or a JWT supplied as the
provider ``api_key``.

Optional: ``LANGFLOW_WXO_LOCAL_API_ROOT`` — after SDK base-URL normalization, all
wxO HTTP clients use this exact root (e.g. ``http://localhost:4321/orchestrate``)
when paths in your gateway do not match the default ``.../v1`` or ``.../v1/orchestrate``
suffix from ``ibm_watsonx_orchestrate_clients``.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

_LOCAL_DEV_ENV = "LANGFLOW_WXO_LOCAL_DEV"
_BEARER_ENV = "WXO_MCSP_LOCAL_TOKEN"
_API_ROOT_ENV = "LANGFLOW_WXO_LOCAL_API_ROOT"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def wxo_local_dev_enabled() -> bool:
    return os.getenv(_LOCAL_DEV_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def is_wxo_local_instance_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in _LOCAL_HOSTS


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
