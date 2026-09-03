"""Validation utilities for CLI commands."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from lfx.integrations.errors import ConnectionUnresolvedError


def is_valid_env_var_name(name: str) -> bool:
    """Check if a string is a valid environment variable name.

    Environment variable names should:
    - Start with a letter or underscore
    - Contain only letters, numbers, and underscores
    - Not contain spaces or special characters

    Args:
        name: The string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    # Pattern for valid environment variable names
    # Must start with letter or underscore, followed by letters, numbers, or underscores
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    return bool(re.match(pattern, name))


def validate_global_variables_for_env(graph: Graph) -> list[str]:
    """Validate that all global variables with load_from_db=True can be used as environment variables.

    When the database is not available (noop mode), global variables with load_from_db=True
    are loaded from environment variables. This function checks that all such variables
    have names that are valid for environment variables.

    Args:
        graph: The graph to validate

    Returns:
        list[str]: List of error messages for invalid variable names
    """
    from lfx.services.deps import get_settings_service

    errors = []
    settings_service = get_settings_service()

    # Check if we're in noop mode (no database)
    is_noop_mode = settings_service and settings_service.settings.use_noop_database

    if not is_noop_mode:
        # If database is available, no need to validate
        return errors

    # Check all vertices for fields with load_from_db=True
    for vertex in graph.vertices:
        # Get the fields that have load_from_db=True
        load_from_db_fields = getattr(vertex, "load_from_db_fields", [])

        for field_name in load_from_db_fields:
            # Get the value of the field (which should be the variable name)
            field_value = vertex.params.get(field_name)

            if field_value and isinstance(field_value, str) and not is_valid_env_var_name(field_value):
                errors.append(
                    f"Component '{vertex.display_name}' (id: {vertex.id}) has field '{field_name}' "
                    f"with value '{field_value}' that contains invalid characters for an environment "
                    f"variable name. Environment variable names must start with a letter or underscore "
                    f"and contain only letters, numbers, and underscores (no spaces or special characters)."
                )

    return errors


def validate_connection_refs_for_env(graph: Graph) -> list[ConnectionUnresolvedError]:
    """Return typed failures for connection refs absent from headless injection channels."""
    from lfx.integrations.errors import ConnectionUnresolvedError
    from lfx.integrations.models import ConnectionRef
    from lfx.services.variable.request_scope import normalize_parsed_variables
    from lfx.utils.env_var_security import safe_getenv

    errors: list[ConnectionUnresolvedError] = []
    request_variables = normalize_parsed_variables(graph.context.get("request_variables") or {})
    no_env_fallback = bool(graph.context.get("no_env_fallback"))

    for vertex in graph.vertices:
        template = vertex.data.get("node", {}).get("template", {})
        for field_name, field in template.items():
            if not isinstance(field, dict) or field.get("type") != "connection_ref":
                continue
            value = vertex.params.get(field_name, field.get("value"))
            if not value:
                continue
            try:
                ref = ConnectionRef.parse(value)
            except ValueError:
                errors.append(ConnectionUnresolvedError(str(value)))
                continue
            env_key = ref.env_key()
            alias = f"x-langflow-global-var-{env_key.lower().replace('_', '-')}"
            injected = request_variables.get(env_key) or request_variables.get(alias)
            if not injected and not no_env_fallback:
                injected = safe_getenv(env_key) or safe_getenv(alias)
            if not injected:
                errors.append(ConnectionUnresolvedError(ref.to_handle(), env_key=env_key, provider=ref.provider))
    return errors
