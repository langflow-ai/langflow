"""Startup security-posture warnings for high-impact permissive configurations.

These helpers inspect the resolved settings and return an operator-facing warning
string (or ``None``) so they can be unit-tested without booting the app. The
lifespan logs whatever they return.
"""

from __future__ import annotations

from typing import Any

# Kept as a module constant so tests can assert the exact remediation guidance
# without pinning the full sentence.
CUSTOM_COMPONENT_EXECUTION_WARNING = (
    "SECURITY: Langflow is running in multi-user mode (LANGFLOW_AUTO_LOGIN=false) with "
    "custom components enabled for every user (LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true, "
    "LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=false). Component code is executed on the server "
    "at flow-build time, so any active non-admin user can run arbitrary code on this host. "
    "Restrict this by setting LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=true (only admins may "
    "author component code) or LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false (only built-in server "
    "components run). For untrusted or multi-tenant deployments, also enable hardware "
    "isolation with LANGFLOW_SANDBOX_BACKEND. "
    "See https://docs.langflow.org/deployment-block-custom-components#multi-user-code-execution"
)


def custom_component_execution_warning(settings_service: Any) -> str | None:
    """Return a warning when every regular user can execute arbitrary component code.

    The warning fires only when *all three* hold, i.e. the deployment is genuinely
    exposed rather than merely using the feature:

    * ``AUTO_LOGIN`` is disabled — multi-user mode, so non-admin accounts exist and the
      single-superuser development posture does not apply;
    * ``allow_custom_components`` is enabled — stored component code is ``exec()``d at build;
    * ``custom_component_admin_only`` is disabled — regular editors, not just admins, may
      author that code.

    Returns ``None`` (no warning) for the single-user default (``AUTO_LOGIN=true``) and for
    any deployment that has already applied one of the two lockdowns. Missing attributes are
    read with the same defaults the settings models declare, so a partial/mock settings object
    never raises here.
    """
    auth_settings = getattr(settings_service, "auth_settings", None)
    settings = getattr(settings_service, "settings", None)
    if auth_settings is None or settings is None:
        return None

    auto_login = getattr(auth_settings, "AUTO_LOGIN", True)
    allow_custom_components = getattr(settings, "allow_custom_components", True)
    admin_only = getattr(settings, "custom_component_admin_only", False)

    if auto_login or not allow_custom_components or admin_only:
        return None

    return CUSTOM_COMPONENT_EXECUTION_WARNING
