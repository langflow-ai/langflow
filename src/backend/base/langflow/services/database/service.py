from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import sqlalchemy as sa
from alembic import command, util
from alembic.config import Config
from loguru import logger
from sqlalchemy import event, inspect
from sqlalchemy.dialects import sqlite as dialect_sqlite
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.base import Service
from langflow.services.database import models
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.utils import Result, TableResults
from langflow.services.deps import get_settings_service
from langflow.services.utils import teardown_superuser

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class DatabaseService(Service):
    name = "database_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        if settings_service.settings.database_url is None:
            msg = "No database URL provided"
            raise ValueError(msg)
        self.database_url: str = settings_service.settings.database_url
        self._sanitize_database_url()

        # This file is in langflow.services.database.manager.py
        # the ini is in langflow
        langflow_dir = Path(__file__).parent.parent.parent
        self.script_location = langflow_dir / "alembic"
        self.alembic_cfg_path = langflow_dir / "alembic.ini"

        # register the event listener for sqlite as part of this class.
        # Using decorator will make the method not able to use self
        event.listen(Engine, "connect", self.on_connection)
        self.engine = self._create_engine()

        alembic_log_file = self.settings_service.settings.alembic_log_file
        # Check if the provided path is absolute, cross-platform.
        if Path(alembic_log_file).is_absolute():
            self.alembic_log_path = Path(alembic_log_file)
        else:
            self.alembic_log_path = Path(langflow_dir) / alembic_log_file

        self._logged_pragma = False

    async def initialize_alembic_log_file(self):
        # Ensure the directory and file for the alembic log file exists
        await anyio.Path(self.alembic_log_path.parent).mkdir(parents=True, exist_ok=True)
        await anyio.Path(self.alembic_log_path).touch(exist_ok=True)

    def reload_engine(self) -> None:
        self._sanitize_database_url()
        self.engine = self._create_engine()

    def _sanitize_database_url(self):
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://")
            logger.warning(
                "Fixed postgres dialect in database URL. Replacing postgres:// with postgresql://. "
                "To avoid this warning, update the database URL."
            )

    def _create_engine(self) -> AsyncEngine:
        """Create the engine for the database."""
        url_components = self.database_url.split("://", maxsplit=1)
        if url_components[0].startswith("sqlite"):
            database_url = "sqlite+aiosqlite://"
            kwargs = {}
        else:
            kwargs = {
                "pool_size": self.settings_service.settings.pool_size,
                "max_overflow": self.settings_service.settings.max_overflow,
            }
            database_url = "postgresql+psycopg://" if url_components[0].startswith("postgresql") else url_components[0]
        database_url += url_components[1]
        return create_async_engine(
            database_url,
            connect_args=self._get_connect_args(),
            **kwargs,
        )

    def _get_connect_args(self):
        if self.settings_service.settings.database_url and self.settings_service.settings.database_url.startswith(
            "sqlite"
        ):
            connect_args = {
                "check_same_thread": False,
                "timeout": self.settings_service.settings.db_connect_timeout,
            }
        else:
            connect_args = {}
        return connect_args

    def on_connection(self, dbapi_connection, _connection_record) -> None:
        if isinstance(dbapi_connection, sqlite3.Connection | dialect_sqlite.aiosqlite.AsyncAdapt_aiosqlite_connection):
            pragmas: dict = self.settings_service.settings.sqlite_pragmas or {}
            pragmas_list = []
            for key, val in pragmas.items():
                pragmas_list.append(f"PRAGMA {key} = {val}")
            if not self._logged_pragma:
                logger.debug(f"sqlite connection, setting pragmas: {pragmas_list}")
                self._logged_pragma = True
            if pragmas_list:
                cursor = dbapi_connection.cursor()
                try:
                    for pragma in pragmas_list:
                        try:
                            cursor.execute(pragma)
                        except OperationalError:
                            logger.exception(f"Failed to set PRAGMA {pragma}")
                finally:
                    cursor.close()

    @asynccontextmanager
    async def with_session(self):
        async with AsyncSession(self.engine, expire_on_commit=False) as session:
            yield session

    async def assign_orphaned_flows_to_superuser(self) -> None:
        """Assign orphaned flows to the default superuser when auto login is enabled."""
        settings_service = get_settings_service()

        if not settings_service.auth_settings.AUTO_LOGIN:
            return

        async with self.with_session() as session:
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

            logger.debug("Assigning orphaned flows to the default superuser")

            # Retrieve superuser
            superuser_username = settings_service.auth_settings.SUPERUSER
            superuser = await get_user_by_username(session, superuser_username)

            if not superuser:
                error_message = "Default superuser not found"
                logger.error(error_message)
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
            logger.debug("Successfully assigned orphaned flows to the default superuser")

    def _generate_unique_flow_name(self, original_name: str, existing_names: set[str]) -> str:
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

    def _check_schema_health(self, connection) -> bool:
        inspector = inspect(connection)

        model_mapping: dict[str, type[SQLModel]] = {
            "flow": models.Flow,
            "user": models.User,
            "apikey": models.ApiKey,
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
        async with self.with_session() as session, session.bind.connect() as conn:
            await conn.run_sync(self._check_schema_health)

    def init_alembic(self, alembic_cfg) -> None:
        logger.info("Initializing alembic")
        command.ensure_version(alembic_cfg)
        # alembic_cfg.attributes["connection"].commit()
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic initialized")

    def _run_migrations(self, should_initialize_alembic, fix) -> None:
        # First we need to check if alembic has been initialized
        # If not, we need to initialize it
        # if not self.script_location.exists(): # this is not the correct way to check if alembic has been initialized
        # We need to check if the alembic_version table exists
        # if not, we need to initialize alembic
        # stdout should be something like sys.stdout
        # which is a buffer
        # I don't want to output anything
        # subprocess.DEVNULL is an int
        with self.alembic_log_path.open("w", encoding="utf-8") as buffer:
            alembic_cfg = Config(stdout=buffer)
            # alembic_cfg.attributes["connection"] = session
            alembic_cfg.set_main_option("script_location", str(self.script_location))
            alembic_cfg.set_main_option("sqlalchemy.url", self.database_url.replace("%", "%%"))

            if should_initialize_alembic:
                try:
                    self.init_alembic(alembic_cfg)
                except Exception as exc:
                    msg = "Error initializing alembic"
                    logger.exception(msg)
                    raise RuntimeError(msg) from exc
            else:
                logger.info("Alembic already initialized")

            logger.info(f"Running DB migrations in {self.script_location}")

            try:
                buffer.write(f"{datetime.now(tz=timezone.utc).astimezone().isoformat()}: Checking migrations\n")
                command.check(alembic_cfg)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Error checking migrations: {exc}")
                if isinstance(exc, util.exc.CommandError | util.exc.AutogenerateDiffsDetected):
                    command.upgrade(alembic_cfg, "head")
                    time.sleep(3)

            try:
                buffer.write(f"{datetime.now(tz=timezone.utc).astimezone()}: Checking migrations\n")
                command.check(alembic_cfg)
            except util.exc.AutogenerateDiffsDetected as exc:
                logger.exception("Error checking migrations")
                if not fix:
                    msg = f"There's a mismatch between the models and the database.\n{exc}"
                    raise RuntimeError(msg) from exc

            if fix:
                self.try_downgrade_upgrade_until_success(alembic_cfg)

    async def run_migrations(self, *, fix=False) -> None:
        should_initialize_alembic = False
        async with self.with_session() as session:
            # If the table does not exist it throws an error
            # so we need to catch it
            try:
                await session.exec(text("SELECT * FROM alembic_version"))
            except Exception:  # noqa: BLE001
                logger.debug("Alembic not initialized")
                should_initialize_alembic = True
        await asyncio.to_thread(self._run_migrations, should_initialize_alembic, fix)

    def try_downgrade_upgrade_until_success(self, alembic_cfg, retries=5) -> None:
        # Try -1 then head, if it fails, try -2 then head, etc.
        # until we reach the number of retries
        for i in range(1, retries + 1):
            try:
                command.check(alembic_cfg)
                break
            except util.exc.AutogenerateDiffsDetected:
                # downgrade to base and upgrade again
                logger.warning("AutogenerateDiffsDetected")
                command.downgrade(alembic_cfg, f"-{i}")
                # wait for the database to be ready
                time.sleep(3)
                command.upgrade(alembic_cfg, "head")

    async def run_migrations_test(self):
        # This method is used for testing purposes only
        # We will check that all models are in the database
        # and that the database is up to date with all columns
        # get all models that are subclasses of SQLModel
        sql_models = [
            model for model in models.__dict__.values() if isinstance(model, type) and issubclass(model, SQLModel)
        ]
        async with self.with_session() as session, session.bind.connect() as conn:
            return [
                TableResults(sql_model.__tablename__, conn.run_sync(self.check_table, sql_model))
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
        from sqlalchemy import inspect

        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        current_tables = ["flow", "user", "apikey", "folder", "message", "variable", "transaction", "vertex_build"]

        if table_names and all(table in table_names for table in current_tables):
            logger.debug("Database and tables already exist")
            return

        logger.debug("Creating database and tables")

        for table in SQLModel.metadata.sorted_tables:
            try:
                table.create(connection, checkfirst=True)
            except OperationalError as oe:
                logger.warning(f"Table {table} already exists, skipping. Exception: {oe}")
            except Exception as exc:
                msg = f"Error creating table {table}"
                logger.exception(msg)
                raise RuntimeError(msg) from exc

        # Now check if the required tables exist, if not, something went wrong.
        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        for table in current_tables:
            if table not in table_names:
                logger.error("Something went wrong creating the database and tables.")
                logger.error("Please check your database settings.")
                msg = "Something went wrong creating the database and tables."
                raise RuntimeError(msg)

        logger.debug("Database and tables created successfully")

    async def create_db_and_tables(self) -> None:
        async with self.with_session() as session, session.bind.connect() as conn:
            await conn.run_sync(self._create_db_and_tables)

    async def teardown(self) -> None:
        logger.debug("Tearing down database")
        try:
            settings_service = get_settings_service()
            # remove the default superuser if auto_login is enabled
            # using the SUPERUSER to get the user
            async with self.with_session() as session:
                await teardown_superuser(settings_service, session)
        except Exception:  # noqa: BLE001
            logger.exception("Error tearing down database")
        await self.engine.dispose()
