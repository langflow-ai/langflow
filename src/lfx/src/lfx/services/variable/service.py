"""Minimal variable service for lfx package with in-memory storage and environment fallback."""

import json
import os

from lfx.log.logger import logger
from lfx.services.base import Service


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
        """Parse request-scoped variables from LANGFLOW_REQUEST_VARIABLES when available."""
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
        return {str(key): str(value) for key, value in parsed.items()}

    async def get_variable(self, name: str, **kwargs) -> str | None:  # noqa: ARG002
        """Get a variable value.

        First checks in-memory cache, then LANGFLOW_REQUEST_VARIABLES, then
        environment variables, then ``x-langflow-global-var-*`` normalized keys.

        Async to match the call signature in custom_component.get_variable
        (`await variable_service.get_variable(...)`), which is the path used
        by component variable resolution. The lookup itself is sync — no I/O —
        but the coroutine wrapper is required so callers can `await` it
        regardless of which variable service implementation is registered
        (lfx env-fallback vs langflow DB-backed).

        Args:
            name: Variable name
            **kwargs: Additional arguments (ignored; user_id/field/session
                from langflow's call signature are absorbed and not used,
                since this implementation has no per-user scope).

        Returns:
            Variable value or None if not found
        """
        # Check in-memory first
        if name in self._variables:
            return self._variables[name]

        # Contract-first: prefer request-scoped variables injected by runtime.
        request_variables = self._get_request_variables()
        if name in request_variables:
            logger.debug(f"Variable '{name}' loaded from LANGFLOW_REQUEST_VARIABLES")
            return request_variables[name]

        # Fall back to environment variable
        value = os.getenv(name)
        if value:
            logger.debug(f"Variable '{name}' loaded from environment")
            return value

        # Fall back to x-langflow-global-var-* aliases
        global_alias = self._normalize_global_var_key(name)
        value = os.getenv(global_alias)
        if value:
            logger.debug(f"Variable '{name}' loaded from global alias '{global_alias}'")
            return value

        return None

    def set_variable(self, name: str, value: str, **kwargs) -> None:  # noqa: ARG002
        """Set a variable value (in-memory only).

        Args:
            name: Variable name
            value: Variable value
            **kwargs: Additional arguments (ignored in minimal implementation)
        """
        self._variables[name] = value
        logger.debug(f"Variable '{name}' set (in-memory only)")

    def delete_variable(self, name: str, **kwargs) -> None:  # noqa: ARG002
        """Delete a variable (from in-memory cache only).

        Args:
            name: Variable name
            **kwargs: Additional arguments (ignored in minimal implementation)
        """
        if name in self._variables:
            del self._variables[name]
            logger.debug(f"Variable '{name}' deleted (from in-memory cache)")

    def list_variables(self, **kwargs) -> list[str]:  # noqa: ARG002
        """List all variables (in-memory only).

        Args:
            **kwargs: Additional arguments (ignored in minimal implementation)

        Returns:
            List of variable names
        """
        return list(self._variables.keys())

    async def teardown(self) -> None:
        """Teardown the variable service."""
        self._variables.clear()
        logger.debug("Variable service teardown")
