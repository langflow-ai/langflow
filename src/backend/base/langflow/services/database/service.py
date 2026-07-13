"""langflow's DatabaseService: a thin subclass over lfx's Tier 1 service.

The engine/session/migration *mechanism* now lives in
``lfx.services.database.service.DatabaseService`` (the Tier 1 infrastructure
port). langflow subclasses it to:

* drive its **own** alembic lineage (``script_location`` -> ``langflow/alembic``,
  version table ``alembic_version``), which owns the full schema; and
* add its domain bootstrap (superuser assignment, schema-health checks) that
  references langflow-domain models.

This is an intentional "override" -- the exception the convergence rule allows --
because langflow's migration lineage and domain policy genuinely differ from a
bare ``lfx serve``. Everything else is inherited. The module also re-exports the
symbols callers historically imported from here so existing imports keep working.
See ``src/lfx/PLUGGABLE_SERVICES.md`` (two-stream migration model).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

import sqlalchemy as sa
from lfx.log.logger import logger
from lfx.services.database.service import (
    DatabaseService as LfxDatabaseService,
)
from lfx.services.database.service import (
    UnsupportedPostgreSQLVersionError,
    check_postgresql_version_sync,
    check_sqlite_database_path,
    get_sqlite_database_file_path,
)
from lfx.services.deps import session_scope
from sqlalchemy import inspect
from sqlmodel import SQLModel, select

from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.database import models
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.utils import Result, TableResults
from langflow.services.deps import get_settings_service
from langflow.services.utils import teardown_superuser

# Re-exported for backward compatibility (historical import site).
__all__ = [
    "DatabaseService",
    "SQLModel",
    "UnsupportedPostgreSQLVersionError",
    "check_postgresql_version_sync",
    "check_sqlite_database_path",
    "get_sqlite_database_file_path",
]


class DatabaseService(LfxDatabaseService):
    """langflow's Tier 1 database service: lfx engine/migration core + domain bootstrap."""

    # langflow owns the full schema through its historical lineage; keep the
    # default alembic version table so existing databases are recognised.
    alembic_version_table: ClassVar[str] = "alembic_version"
    # The tables langflow provisions via create_db_and_tables sanity check.
    expected_tables: ClassVar[tuple[str, ...]] = (
        "flow",
        "user",
        "apikey",
        "folder",
        "message",
        "variable",
        "transaction",
        "vertex_build",
        "job",
    )

    def _resolve_script_location(self) -> Path:
        """Point the migration runner at langflow's own alembic tree."""
        langflow_dir = Path(__file__).parent.parent.parent
        return langflow_dir / "alembic"

    async def assign_orphaned_flows_to_superuser(self) -> None:
        """Assign orphaned flows to the default superuser when auto login is enabled."""
        settings_service = get_settings_service()

        if not settings_service.auth_settings.AUTO_LOGIN:
            return

        async with session_scope() as session:
            # Fetch orphaned flows
            stmt = (
                select(models.Flow)
                .join(models.Folder)
                .where(
                    models.Flow.user_id == None,  # noqa: E711
                    models.Folder.name != STARTER_FOLDER_NAME,
                )
            )
            orphaned_flows = (await session.exec(stmt)).all()

            if not orphaned_flows:
                return

            await logger.adebug("Assigning orphaned flows to the default superuser")

            # Retrieve superuser
            superuser_username = settings_service.auth_settings.SUPERUSER
            superuser = await get_user_by_username(session, superuser_username)

            if not superuser:
                error_message = "Default superuser not found"
                await logger.aerror(error_message)
                raise RuntimeError(error_message)

            # Get existing flow names for the superuser
            existing_names: set[str] = set(
                (await session.exec(select(models.Flow.name).where(models.Flow.user_id == superuser.id))).all()
            )

            # Process orphaned flows
            for flow in orphaned_flows:
                flow.user_id = superuser.id
                flow.name = self._generate_unique_flow_name(flow.name, existing_names)
                existing_names.add(flow.name)
                session.add(flow)

            # Commit changes
            await session.commit()
            await logger.adebug("Successfully assigned orphaned flows to the default superuser")

    @staticmethod
    def _generate_unique_flow_name(original_name: str, existing_names: set[str]) -> str:
        """Generate a unique flow name by adding or incrementing a suffix."""
        if original_name not in existing_names:
            return original_name

        match = re.search(r"^(.*) \((\d+)\)$", original_name)
        if match:
            base_name, current_number = match.groups()
            new_name = f"{base_name} ({int(current_number) + 1})"
        else:
            new_name = f"{original_name} (1)"

        # Ensure unique name by incrementing suffix
        while new_name in existing_names:
            match = re.match(r"^(.*) \((\d+)\)$", new_name)
            if match is not None:
                base_name, current_number = match.groups()
            else:
                error_message = "Invalid format: match is None"
                raise ValueError(error_message)

            new_name = f"{base_name} ({int(current_number) + 1})"

        return new_name

    @staticmethod
    def _check_schema_health(connection) -> bool:
        inspector = inspect(connection)

        model_mapping: dict[str, type[SQLModel]] = {
            "flow": models.Flow,
            "user": models.User,
            "apikey": models.ApiKey,
            "job": models.Job,
            # Add other SQLModel classes here
        }

        # To account for tables that existed in older versions
        legacy_tables = ["flowstyle"]

        for table, model in model_mapping.items():
            expected_columns = list(model.model_fields.keys())

            try:
                available_columns = [col["name"] for col in inspector.get_columns(table)]
            except sa.exc.NoSuchTableError:
                logger.debug(f"Missing table: {table}")
                return False

            for column in expected_columns:
                if column not in available_columns:
                    logger.debug(f"Missing column: {column} in table {table}")
                    return False

        for table in legacy_tables:
            if table in inspector.get_table_names():
                logger.warning(f"Legacy table exists: {table}")

        return True

    async def check_schema_health(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(self._check_schema_health)

    async def run_migrations_test(self):
        # This method is used for testing purposes only
        # We will check that all models are in the database
        # and that the database is up to date with all columns
        sql_models = [
            model for model in models.__dict__.values() if isinstance(model, type) and issubclass(model, SQLModel)
        ]
        # Use engine.begin() for proper async connection management with NullPool
        async with self.engine.begin() as conn:
            return [
                TableResults(sql_model.__tablename__, await conn.run_sync(self.check_table, sql_model))
                for sql_model in sql_models
            ]

    @staticmethod
    def check_table(connection, model):
        results = []
        inspector = inspect(connection)
        table_name = model.__tablename__
        expected_columns = list(model.__fields__.keys())
        available_columns = []
        try:
            available_columns = [col["name"] for col in inspector.get_columns(table_name)]
            results.append(Result(name=table_name, type="table", success=True))
        except sa.exc.NoSuchTableError:
            logger.exception(f"Missing table: {table_name}")
            results.append(Result(name=table_name, type="table", success=False))

        for column in expected_columns:
            if column not in available_columns:
                logger.error(f"Missing column: {column} in table {table_name}")
                results.append(Result(name=column, type="column", success=False))
            else:
                results.append(Result(name=column, type="column", success=True))
        return results

    @staticmethod
    def _create_db_and_tables(connection) -> None:
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(connection)
        table_names = inspector.get_table_names()
        current_tables = [
            "flow",
            "user",
            "apikey",
            "folder",
            "message",
            "variable",
            "transaction",
            "vertex_build",
            "job",
        ]

        if table_names and all(table in table_names for table in current_tables):
            logger.debug("Database and tables already exist")
            return

        logger.debug("Creating database and tables")

        for table in SQLModel.metadata.sorted_tables:
            try:
                table.create(connection, checkfirst=True)
            except sa.exc.OperationalError as oe:
                logger.warning(f"Table {table} already exists, skipping. Exception: {oe}")
            except Exception as exc:
                msg = f"Error creating table {table}"
                logger.exception(msg)
                raise RuntimeError(msg) from exc

        # Now check if the required tables exist, if not, something went wrong.
        inspector = sa_inspect(connection)
        table_names = inspector.get_table_names()
        for table in current_tables:
            if table not in table_names:
                logger.error("Something went wrong creating the database and tables.")
                logger.error("Please check your database settings.")
                msg = "Something went wrong creating the database and tables."
                raise RuntimeError(msg)

        logger.debug("Database and tables created successfully")

    async def teardown(self) -> None:
        await logger.adebug("Tearing down database")
        try:
            settings_service = get_settings_service()
            # When AUTO_LOGIN is off, remove the unused default superuser (see teardown_superuser).
            async with session_scope() as session:
                await teardown_superuser(settings_service, session)
        except Exception:
            await logger.aexception("Error tearing down database")
            raise
        finally:
            await self.engine.dispose()
