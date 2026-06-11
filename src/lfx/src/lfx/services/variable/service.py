"""Minimal variable service for lfx package with in-memory storage and environment fallback."""

import json
import os

from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.variable.request_scope import (
    get_active_request_variables,
    is_env_fallback_disabled,
    normalize_parsed_variables,
)


class VariableService(Service):
    """Minimal variable service with in-memory storage and environment fallback.

    This is a lightweight implementation for LFX that maintains in-memory
    variables and falls back to environment variables for reads. No database storage.

    """

    name = "variable_service"

    def __init__(self) -> None:
        """Initialize the variable service."""
        super().__init__()
        self._variables: dict[str, str] = {}
        self.set_ready()
        logger.debug("Variable service initialized (env vars only)")

    @staticmethod
    def _normalize_global_var_key(name: str) -> str:
        return f"x-langflow-global-var-{name.lower().replace('_', '-')}"

    @staticmethod
    def _get_request_variables() -> dict[str, str]:
        """Request-scoped variables from serve ContextVar or LANGFLOW_REQUEST_VARIABLES env."""
        active = get_active_request_variables()
        if active is not None:
            return active

        # LANGFLOW_REQUEST_VARIABLES is a process-wide env var, so reading it is an
        # os.environ access. Honor the no-env-fallback contract and skip it when the
        # request disables env fallback, keeping the "never reads os.environ" guarantee.
        if is_env_fallback_disabled():
            return {}

        raw = os.getenv("LANGFLOW_REQUEST_VARIABLES")
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Invalid LANGFLOW_REQUEST_VARIABLES JSON; skipping request-scoped lookup")
            return {}
        if not isinstance(parsed, dict):
            logger.debug("LANGFLOW_REQUEST_VARIABLES must be a JSON object; skipping request-scoped lookup")
            return {}
        return normalize_parsed_variables(parsed)

    async def get_variable(self, name: str, **kwargs) -> str | None:  # noqa: ARG002
        """Get a variable value.

        Resolution order (first match wins):
          1. In-memory cache (``set_variable``).
          2. Request-scoped exact name (serve ContextVar or ``LANGFLOW_REQUEST_VARIABLES``).
          3. Request-scoped ``x-langflow-global-var-*`` alias.
          4. Environment variable (exact name).
          5. Environment variable (``x-langflow-global-var-*`` alias).

        Both request-scoped lookups (2, 3) run *before* any process-env fallback (4, 5),
        so a credential the caller supplies for this request — in either the exact-name
        or the ``x-langflow-global-var-*`` form — always beats a same-named variable left
        in the worker's environment, preventing one caller's request from running on an
        ambient process credential.

        When the active request disables env fallback (``graph.context['no_env_fallback']``,
        propagated via the request scope), steps 4 and 5 are skipped so resolution
        never reads ``os.environ`` — matching ``load_from_env_vars`` for ``load_from_db``
        fields and keeping served flows isolated from process-wide credentials.
        """
        if name in self._variables:
            return self._variables[name]

        request_variables = self._get_request_variables()
        if name in request_variables:
            logger.debug(f"Variable '{name}' loaded from request-scoped variables")
            return request_variables[name]

        global_alias = self._normalize_global_var_key(name)
        if global_alias in request_variables:
            logger.debug(f"Variable '{name}' loaded from request-scoped alias '{global_alias}'")
            return request_variables[global_alias]

        if not is_env_fallback_disabled():
            value = os.getenv(name)
            if value:
                logger.debug(f"Variable '{name}' loaded from environment")
                return value

            value = os.getenv(global_alias)
            if value:
                logger.debug(f"Variable '{name}' loaded from global alias '{global_alias}'")
                return value

        return None

    def set_variable(self, name: str, value: str, **kwargs) -> None:  # noqa: ARG002
        """Set a variable value (in-memory only)."""
        self._variables[name] = value
        logger.debug(f"Variable '{name}' set (in-memory only)")

    def delete_variable(self, name: str, **kwargs) -> None:  # noqa: ARG002
        """Delete a variable (from in-memory cache only)."""
        if name in self._variables:
            del self._variables[name]
            logger.debug(f"Variable '{name}' deleted (from in-memory cache)")

    def list_variables(self, **kwargs) -> list[str]:  # noqa: ARG002
        """List all variables (in-memory only)."""
        return list(self._variables.keys())

    async def teardown(self) -> None:
        """Teardown the variable service."""
        self._variables.clear()
        logger.debug("Variable service teardown")
