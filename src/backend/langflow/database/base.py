from contextlib import contextmanager
import os

from sqlmodel import SQLModel, Session, create_engine
from langflow.utils.logger import logger
import sqlalchemy as sa


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

    @classmethod
    def teardown(cls):
        logger.debug("Tearing down database engine")
        if cls._instance is not None:
            cls._instance.dispose()
        cls._instance = None


def create_db_and_tables():
    logger.debug("Creating database and tables")
    try:
        SQLModel.metadata.create_all(Engine.get())
    except sa.exc.OperationalError as exc:
        # Check if the error is because the table already exists
        if "already exists" in str(exc):
            logger.debug("Database and tables already exist")
        else:
            logger.error(f"Error creating database and tables: {exc}")
            raise RuntimeError("Error creating database and tables") from exc
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


@contextmanager
def session_getter():
    try:
        session = Session(Engine.get())
        yield session
    except Exception as e:
        print("Session rollback because of exception:", e)
        session.rollback()
        raise
    finally:
        session.close()


def get_session():
    with session_getter() as session:
        yield session
