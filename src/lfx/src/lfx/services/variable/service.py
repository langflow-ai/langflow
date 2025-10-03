"""Minimal variable service for lfx package - environment variables only."""

import os

from lfx.log.logger import logger
from lfx.services.base import Service


class VariableService(Service):
    """Minimal variable service using environment variables.

    This is a lightweight implementation for LFX that only reads
    from environment variables. No database storage.
    """

    name = "variable_service"

    def __init__(self) -> None:
        """Initialize the variable service."""
        super().__init__()
        self._variables: dict[str, str] = {}
        self.set_ready()
        logger.debug("Variable service initialized (env vars only)")

    def get_variable(self, name: str, **kwargs) -> str | None:  # noqa: ARG002
        """Get a variable value.

        First checks in-memory cache, then environment variables.

        Args:
            name: Variable name
            **kwargs: Additional arguments (ignored in minimal implementation)

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
