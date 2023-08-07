from pathlib import Path
from langflow.services.base import Service
from sqlmodel import SQLModel, Session, create_engine
from langflow.utils.logger import logger
from alembic.config import Config
from alembic import command
from langflow.services.database import models  # noqa


class DatabaseManager(Service):
    name = "database_manager"

    def __init__(self, database_url: str):
        self.database_url = database_url
        # This file is in langflow.services.database.manager.py
        # the ini is in langflow
        langflow_dir = Path(__file__).parent.parent.parent
        self.script_location = langflow_dir / "alembic"
        self.alembic_cfg_path = langflow_dir / "alembic.ini"
        self.engine = create_engine(database_url)

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

    def run_migrations(self):
        logger.info(
            f"Running DB migrations in {self.script_location} on {self.database_url}"
        )
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(self.script_location))
        alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)
        command.upgrade(alembic_cfg, "head")

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
        if "flow" not in inspector.get_table_names():
            logger.error("Something went wrong creating the database and tables.")
            logger.error("Please check your database settings.")
            raise RuntimeError("Something went wrong creating the database and tables.")
        else:
            logger.debug("Database and tables created successfully")
