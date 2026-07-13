"""Helper for Windows + PostgreSQL event loop configuration.

The implementation moved to ``lfx.utils.windows_postgres_helper`` when the Tier 1
DatabaseService was extracted into lfx. This shim preserves the historical
``langflow.helpers.windows_postgres_helper`` import path.
"""

from lfx.utils.windows_postgres_helper import (
    LANGFLOW_DATABASE_URL,
    POSTGRESQL_PREFIXES,
    configure_windows_postgres_event_loop,
)

__all__ = [
    "LANGFLOW_DATABASE_URL",
    "POSTGRESQL_PREFIXES",
    "configure_windows_postgres_event_loop",
]
