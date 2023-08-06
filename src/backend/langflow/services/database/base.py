from contextlib import contextmanager
import os
from pathlib import Path
from langflow.services.base import Service
from sqlmodel import SQLModel, Session, create_engine
from langflow.utils.logger import logger
from alembic.config import Config
from alembic import command


class Engine:
    _instance = None

    @classmethod
    def get(cls):
        logger.debug("Getting database engine")
        if cls._instance is None:
            cls.create()
        return cls._instance

    @classmethod
    def create(cls):
        logger.debug("Creating database engine")
        from langflow.settings import settings

        if langflow_database_url := os.getenv("LANGFLOW_DATABASE_URL"):
            settings.DATABASE_URL = langflow_database_url
            logger.debug("Using LANGFLOW_DATABASE_URL")

        if settings.DATABASE_URL and settings.DATABASE_URL.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {}
        if not settings.DATABASE_URL:
            raise RuntimeError("No database_url provided")
        cls._instance = create_engine(settings.DATABASE_URL, connect_args=connect_args)

    @classmethod
    def update(cls):
        logger.debug("Updating database engine")
        cls._instance = None
        cls.create()


def create_db_and_tables():
    logger.debug("Creating database and tables")
    try:
        SQLModel.metadata.create_all(Engine.get())
    except Exception as exc:
        logger.error(f"Error creating database and tables: {exc}")
        raise RuntimeError("Error creating database and tables") from exc
    # Now check if the table Flow exists, if not, something went wrong
    # and we need to create the tables again.
    from sqlalchemy import inspect

    inspector = inspect(Engine.get())
    if "flow" not in inspector.get_table_names():
        logger.error("Something went wrong creating the database and tables.")
        logger.error("Please check your database settings.")

        raise RuntimeError("Something went wrong creating the database and tables.")
    else:
        logger.debug("Database and tables created successfully")


class DatabaseManager(Service):
    name = "database_manager"

    def __init__(self, database_url: str):
        self.database_url = database_url
        # This file is in langflow.services.database.base.py
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


@contextmanager
def session_getter(db_manager: DatabaseManager):
    try:
        session = Session(DatabaseManager.engine)
        yield session
    except Exception as e:
        print("Session rollback because of exception:", e)
        session.rollback()
        raise
    finally:
        session.close()


def get_session():
    with Session(Engine.get()) as session:
        yield session


def initialize_database():
    logger.debug("Initializing database")
    from langflow.services import service_manager, ServiceType

    database_manager = service_manager.get(ServiceType.DATABASE_MANAGER)
    database_manager.run_migrations()
    database_manager.create_db_and_tables()
    logger.debug("Database initialized")
