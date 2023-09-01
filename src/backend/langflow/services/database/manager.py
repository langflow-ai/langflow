from pathlib import Path
from typing import TYPE_CHECKING
from langflow.services.base import Service
from langflow.services.database.models.user.crud import get_user_by_username
from langflow.services.database.utils import Result, TableResults
from langflow.services.utils import get_settings_manager
from sqlalchemy import inspect
import sqlalchemy as sa
from sqlmodel import SQLModel, Session, create_engine
from langflow.utils.logger import logger
from alembic.config import Config
from alembic import command
from langflow.services.database import models  # noqa

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class DatabaseManager(Service):
    name = "database_manager"

    def __init__(self, database_url: str):
        self.database_url = database_url
        # This file is in langflow.services.database.manager.py
        # the ini is in langflow
        langflow_dir = Path(__file__).parent.parent.parent
        self.script_location = langflow_dir / "alembic"
        self.alembic_cfg_path = langflow_dir / "alembic.ini"
        self.engine = self._create_engine()

    def _create_engine(self) -> "Engine":
        """Create the engine for the database."""
        settings_manager = get_settings_manager()
        if (
            settings_manager.settings.DATABASE_URL
            and settings_manager.settings.DATABASE_URL.startswith("sqlite")
        ):
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {}
        return create_engine(self.database_url, connect_args=connect_args)

    def __enter__(self):
        self._session = Session(self.engine)
        return self._session

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:  # If an exception has been raised
            logger.error(
                f"Session rollback because of exception: {exc_type.__name__} {exc_value}"
            )
            self._session.rollback()
        else:
            self._session.commit()
        self._session.close()

    def get_session(self):
        with Session(self.engine) as session:
            yield session

    def check_schema_health(self) -> bool:
        inspector = inspect(self.engine)

        model_mapping = {
            "flow": models.Flow,
            "user": models.User,
            "apikey": models.ApiKey,
            # Add other SQLModel classes here
        }

        # To account for tables that existed in older versions
        legacy_tables = ["flowstyle"]

        for table, model in model_mapping.items():
            expected_columns = list(model.__fields__.keys())

            try:
                available_columns = [
                    col["name"] for col in inspector.get_columns(table)
                ]
            except sa.exc.NoSuchTableError:
                logger.error(f"Missing table: {table}")
                return False

            for column in expected_columns:
                if column not in available_columns:
                    logger.error(f"Missing column: {column} in table {table}")
                    return False

        for table in legacy_tables:
            if table in inspector.get_table_names():
                logger.warn(f"Legacy table exists: {table}")

        return True

    def run_migrations(self):
        logger.info(
            f"Running DB migrations in {self.script_location} on {self.database_url}"
        )
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(self.script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)
        command.upgrade(alembic_cfg, "head")

    def run_migrations_test(self):
        # This method is used for testing purposes only
        # We will check that all models are in the database
        # and that the database is up to date with all columns
        sql_models = [models.Flow, models.User, models.ApiKey]
        results = []
        for sql_model in sql_models:
            results.append(
                TableResults(sql_model.__tablename__, self.check_table(sql_model))
            )
        return results

    def check_table(self, model):
        results = []
        inspector = inspect(self.engine)
        table_name = model.__tablename__
        expected_columns = list(model.__fields__.keys())
        try:
            available_columns = [
                col["name"] for col in inspector.get_columns(table_name)
            ]
            results.append(Result(name=table_name, type="table", success=True))
        except sa.exc.NoSuchTableError:
            logger.error(f"Missing table: {table_name}")
            results.append(Result(name=table_name, type="table", success=False))

        for column in expected_columns:
            if column not in available_columns:
                logger.error(f"Missing column: {column} in table {table_name}")
                results.append(Result(name=column, type="column", success=False))
            else:
                results.append(Result(name=column, type="column", success=True))
        return results

    def create_db_and_tables(self):
        logger.debug("Creating database and tables")
        try:
            SQLModel.metadata.create_all(self.engine)
        except Exception as exc:
            logger.error(f"Error creating database and tables: {exc}")
            raise RuntimeError("Error creating database and tables") from exc

        # Now check if the table "flow" exists, if not, something went wrong
        # and we need to create the tables again.
        from sqlalchemy import inspect

        inspector = inspect(self.engine)
        current_tables = ["flow", "user", "apikey"]
        table_names = inspector.get_table_names()
        for table in current_tables:
            if table not in table_names:
                logger.error("Something went wrong creating the database and tables.")
                logger.error("Please check your database settings.")
                raise RuntimeError(
                    "Something went wrong creating the database and tables."
                )

        logger.debug("Database and tables created successfully")

    def teardown(self):
        logger.debug("Tearing down database")
        try:
            settings_manager = get_settings_manager()
            # remove the default superuser if auto_login is enabled
            # using the FIRST_SUPERUSER to get the user
            if settings_manager.auth_settings.AUTO_LOGIN:
                logger.debug("Removing default superuser")
                username = settings_manager.auth_settings.FIRST_SUPERUSER
                with Session(self.engine) as session:
                    user = get_user_by_username(session, username)
                    session.delete(user)
                    session.commit()
                    logger.debug("Default superuser removed")

        except Exception as exc:
            logger.error(f"Error tearing down database: {exc}")

        self.engine.dispose()
