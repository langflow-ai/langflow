from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import command, util
from alembic.config import Config
from loguru import logger
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine, select, text

from langflow.services.base import Service
from langflow.services.database import models
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.utils import (
    Result,
    TableResults,
)
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
        # This file is in langflow.services.database.manager.py
        # the ini is in langflow
        langflow_dir = Path(__file__).parent.parent.parent
        self.script_location = langflow_dir / "alembic"
        self.alembic_cfg_path = langflow_dir / "alembic.ini"
        self.engine = self._create_engine()
        alembic_log_file = self.settings_service.settings.alembic_log_file

        # Check if the provided path is absolute, cross-platform.
        if Path(alembic_log_file).is_absolute():
            # Use the absolute path directly.
            self.alembic_log_path = Path(alembic_log_file)
        else:
            # Construct the path using the langflow directory.
            self.alembic_log_path = Path(langflow_dir) / alembic_log_file

    def reload_engine(self) -> None:
        self.engine = self._create_engine()

    def _create_engine(self) -> Engine:
        """Create the engine for the database."""
        if self.settings_service.settings.database_url and self.settings_service.settings.database_url.startswith(
            "sqlite"
        ):
            connect_args = {
                "check_same_thread": False,
                "timeout": self.settings_service.settings.db_connect_timeout,
            }
        else:
            connect_args = {}
        try:
            # register the event listener for sqlite as part of this class.
            # Using decorator will make the method not able to use self
            event.listen(Engine, "connect", self.on_connection)

            return create_engine(
                self.database_url,
                connect_args=connect_args,
                pool_size=self.settings_service.settings.pool_size,
                max_overflow=self.settings_service.settings.max_overflow,
            )
        except sa.exc.NoSuchModuleError as exc:
            if "postgres" in str(exc) and not self.database_url.startswith("postgresql"):
                # https://stackoverflow.com/questions/62688256/sqlalchemy-exc-nosuchmoduleerror-cant-load-plugin-sqlalchemy-dialectspostgre
                self.database_url = self.database_url.replace("postgres://", "postgresql://")
                logger.warning(
                    "Fixed postgres dialect in database URL. Replacing postgres:// with postgresql://. "
                    "To avoid this warning, update the database URL."
                )
                return self._create_engine()
            msg = "Error creating database engine"
            raise RuntimeError(msg) from exc

    def on_connection(self, dbapi_connection, _connection_record) -> None:
        from sqlite3 import Connection as sqliteConnection

        if isinstance(dbapi_connection, sqliteConnection):
            pragmas: dict = self.settings_service.settings.sqlite_pragmas or {}
            pragmas_list = []
            for key, val in pragmas.items():
                pragmas_list.append(f"PRAGMA {key} = {val}")
            logger.info(f"sqlite connection, setting pragmas: {pragmas_list}")
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

    @contextmanager
    def with_session(self):
        with Session(self.engine) as session:
            yield session

    def migrate_flows_if_auto_login(self) -> None:
        # if auto_login is enabled, we need to migrate the flows
        # to the default superuser if they don't have a user id
        # associated with them
        settings_service = get_settings_service()
        if settings_service.auth_settings.AUTO_LOGIN:
            with self.with_session() as session:
                flows = session.exec(select(models.Flow).where(models.Flow.user_id is None)).all()
                if flows:
                    logger.debug("Migrating flows to default superuser")
                    username = settings_service.auth_settings.SUPERUSER
                    user = get_user_by_username(session, username)
                    if not user:
                        logger.error("Default superuser not found")
                        msg = "Default superuser not found"
                        raise RuntimeError(msg)
                    for flow in flows:
                        flow.user_id = user.id
                    session.commit()
                    logger.debug("Flows migrated successfully")

    def check_schema_health(self) -> bool:
        inspector = inspect(self.engine)

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

    def init_alembic(self, alembic_cfg) -> None:
        logger.info("Initializing alembic")
        command.ensure_version(alembic_cfg)
        # alembic_cfg.attributes["connection"].commit()
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic initialized")

    def run_migrations(self, *, fix=False) -> None:
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

            should_initialize_alembic = False
            with self.with_session() as session:
                # If the table does not exist it throws an error
                # so we need to catch it
                try:
                    session.exec(text("SELECT * FROM alembic_version"))
                except Exception:  # noqa: BLE001
                    logger.opt(exception=True).info("Alembic not initialized")
                    should_initialize_alembic = True

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
                logger.opt(exception=True).debug("Error checking migrations")
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

    def try_downgrade_upgrade_until_success(self, alembic_cfg, retries=5) -> None:
        # Try -1 then head, if it fails, try -2 then head, etc.
        # until we reach the number of retries
        for i in range(1, retries + 1):
            try:
                command.check(alembic_cfg)
                break
            except util.exc.AutogenerateDiffsDetected:
                # downgrade to base and upgrade again
                logger.opt(exception=True).warning("AutogenerateDiffsDetected")
                command.downgrade(alembic_cfg, f"-{i}")
                # wait for the database to be ready
                time.sleep(3)
                command.upgrade(alembic_cfg, "head")

    def run_migrations_test(self):
        # This method is used for testing purposes only
        # We will check that all models are in the database
        # and that the database is up to date with all columns
        # get all models that are subclasses of SQLModel
        sql_models = [
            model for model in models.__dict__.values() if isinstance(model, type) and issubclass(model, SQLModel)
        ]
        return [TableResults(sql_model.__tablename__, self.check_table(sql_model)) for sql_model in sql_models]

    def check_table(self, model):
        results = []
        inspector = inspect(self.engine)
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

    def create_db_and_tables(self) -> None:
        from sqlalchemy import inspect

        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        current_tables = ["flow", "user", "apikey", "folder", "message", "variable", "transaction", "vertex_build"]

        if table_names and all(table in table_names for table in current_tables):
            logger.debug("Database and tables already exist")
            return

        logger.debug("Creating database and tables")

        for table in SQLModel.metadata.sorted_tables:
            try:
                table.create(self.engine, checkfirst=True)
            except OperationalError as oe:
                logger.warning(f"Table {table} already exists, skipping. Exception: {oe}")
            except Exception as exc:
                msg = f"Error creating table {table}"
                logger.exception(msg)
                raise RuntimeError(msg) from exc

        # Now check if the required tables exist, if not, something went wrong.
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        for table in current_tables:
            if table not in table_names:
                logger.error("Something went wrong creating the database and tables.")
                logger.error("Please check your database settings.")
                msg = "Something went wrong creating the database and tables."
                raise RuntimeError(msg)

        logger.debug("Database and tables created successfully")

    def _teardown(self) -> None:
        logger.debug("Tearing down database")
        try:
            settings_service = get_settings_service()
            # remove the default superuser if auto_login is enabled
            # using the SUPERUSER to get the user
            with self.with_session() as session:
                teardown_superuser(settings_service, session)

        except Exception:  # noqa: BLE001
            logger.exception("Error tearing down database")

        self.engine.dispose()

    async def teardown(self) -> None:
        await asyncio.to_thread(self._teardown)
