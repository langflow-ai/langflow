"""Alembic env.py for the langflow-saas package.

Key design decisions:
  - Connects to the SAME database as Langflow (reads LANGFLOW_DATABASE_URL or
    SAAS_DATABASE_URL override) so saas_* tables live alongside Langflow's tables.
  - Uses ``include_object`` to manage ONLY tables whose names start with
    ``saas_``.  Langflow's own tables are never touched by these migrations.
  - Shares Langflow's ``alembic_version`` table via Alembic branch labels so
    there is no separate version table (avoids the Langflow migration drift check
    flagging an unknown table).
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Resolve database URL.
# SAAS_DATABASE_URL overrides LANGFLOW_DATABASE_URL for scenarios where the
# SaaS tables live in a separate database (advanced multi-DB setups).
# ---------------------------------------------------------------------------
db_url = os.getenv("SAAS_DATABASE_URL") or os.getenv("LANGFLOW_DATABASE_URL") or "sqlite:///./langflow.db"
config.set_main_option("sqlalchemy.url", db_url)

# ---------------------------------------------------------------------------
# Import ALL SaaS models so SQLAlchemy registers them in its metadata before
# Alembic performs autogenerate comparison.
# ---------------------------------------------------------------------------
from langflow_saas.models import (  # noqa: E402 — must be after config setup
    saas_metadata,
)

target_metadata = saas_metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Only manage objects belonging to this plugin.

    Tables must start with ``saas_`` to be managed here; everything else
    (Langflow's tables, Alembic's own version table) is left untouched.
    """
    if type_ == "table":
        return str(name).startswith("saas_")
    # Always include indices, constraints, etc. that belong to managed tables.
    if hasattr(obj, "table"):
        return str(obj.table.name).startswith("saas_")
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        # Use shared alembic_version table via branch labels (no separate table needed).
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            version_table="saas_alembic_version",
            # compare_type=True makes Alembic detect column type changes.
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
