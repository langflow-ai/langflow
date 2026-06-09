"""Minimal variable service for lfx package with in-memory storage and environment fallback."""

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

    async def get_variable(self, name: str, **kwargs) -> str | None:  # noqa: ARG002
        """Get a variable value.

        First checks in-memory cache, then environment variables.

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

        # Fall back to environment variable
        value = os.getenv(name)
        if value:
            logger.debug(f"Variable '{name}' loaded from environment")
        return value

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
