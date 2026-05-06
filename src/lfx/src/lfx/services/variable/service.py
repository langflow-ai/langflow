"""Minimal variable service for lfx package with in-memory storage and environment fallback."""

import json
import os

from lfx.log.logger import logger
from lfx.services.base import Service


class VariableService(Service):
    """Minimal variable service with in-memory storage and environment fallback.

    This is a lightweight implementation for LFX that maintains in-memory
    variables and falls back to environment variables for reads. No database storage.

    Exposes WXO OAuth bearer aliases from environment variables on demand.
    """

    name = "variable_service"

    def __init__(self) -> None:
        """Initialize the variable service."""
        super().__init__()
        self._variables: dict[str, str] = {}
        self.set_ready()
        logger.debug("Variable service initialized (env vars only)")

    @staticmethod
    def _is_wxo_access_token_key(name: str) -> bool:
        """Return True when a variable name matches WXO access-token conventions."""
        normalized = name.lower()
        return normalized.endswith("_access_token") and (
            normalized.startswith("wxo_") or "_wxo_" in normalized
        )

    def _get_wxo_bearer_alias(self, name: str) -> str | None:
        """Resolve a <prefix>_bearer_token alias from matching WXO <prefix>_access_token env var."""
        normalized = name.lower()
        if not normalized.endswith("_bearer_token"):
            return None
        base_name = normalized[: -len("_bearer_token")]
        access_token_name = f"{base_name}_access_token"
        for key, value in os.environ.items():
            if key.lower() == access_token_name and self._is_wxo_access_token_key(key):
                return f"Bearer {value}"
        return None

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

    def _get_wxo_bearer_alias_from_request_variables(self, name: str) -> str | None:
        """Resolve WXO <prefix>_bearer_token alias from request-scoped access token values."""
        normalized = name.lower()
        if not normalized.endswith("_bearer_token"):
            return None
        base_name = normalized[: -len("_bearer_token")]
        access_token_name = f"{base_name}_access_token"
        for key, value in self._get_request_variables().items():
            if key.lower() == access_token_name and self._is_wxo_access_token_key(key):
                return f"Bearer {value}"
        return None

    def get_variable(self, name: str, **kwargs) -> str | None:  # noqa: ARG002
        """Get a variable value.

        First checks in-memory cache, then environment variables, then WXO bearer aliases.

        Args:
            name: Variable name
            **kwargs: Additional arguments (ignored in minimal implementation)

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

        # For WXO OAuth vars, synthesize a <prefix>_bearer_token alias from request variables first.
        bearer_value = self._get_wxo_bearer_alias_from_request_variables(name)
        if bearer_value:
            logger.debug(f"Variable '{name}' synthesized from WXO access token request variable")
            return bearer_value

        # For WXO OAuth vars, synthesize a <prefix>_bearer_token alias on demand.
        bearer_value = self._get_wxo_bearer_alias(name)
        if bearer_value:
            logger.debug(f"Variable '{name}' synthesized from WXO access token environment variable")
            return bearer_value
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
