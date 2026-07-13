"""Database service constants (lfx).

The minimum-PostgreSQL requirement is a property of the *shared* schema, whose
models live in ``lfx.services.database.models``: several tables use
``UNIQUE NULLS DISTINCT``, which only PostgreSQL 15+ supports. Because the schema
is owned here, the version floor is defined here too and langflow re-exports it.
"""

# Minimum PostgreSQL major version required by the lfx/langflow schema.
MIN_POSTGRESQL_MAJOR_VERSION = 15

# User-facing message when migrations fail due to PostgreSQL < 15.
POSTGRESQL_VERSION_REQUIRED_MESSAGE = (
    f"PostgreSQL {MIN_POSTGRESQL_MAJOR_VERSION} or higher is required when using PostgreSQL as the database. "
    "The current PostgreSQL version does not support the syntax used by the schema "
    "(e.g. UNIQUE NULLS DISTINCT). "
    f"Please upgrade your PostgreSQL instance to version {MIN_POSTGRESQL_MAJOR_VERSION} or higher. "
    "See: https://docs.langflow.org/configuration-custom-database"
)
