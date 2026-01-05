"""Validation utilities for CLI commands."""

import re

from lfx.graph.graph.base import Graph
from lfx.services.deps import get_settings_service


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
