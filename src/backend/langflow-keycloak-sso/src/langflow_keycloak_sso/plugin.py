"""Langflow plugin entry point for Keycloak SSO.

Registered via:
    [project.entry-points."langflow.plugins"]
    keycloak-sso = "langflow_keycloak_sso.plugin:register"
"""

from __future__ import annotations

from .router import router


def register(app) -> None:  # type: ignore[no-untyped-def]
    """Register Keycloak SSO routes with the Langflow application.

    Called automatically by Langflow's plugin loader at startup.
    The ``app`` argument is a _PluginAppWrapper that prevents route conflicts.
    """
    app.include_router(router)
