from dataclasses import dataclass
from typing import TYPE_CHECKING
from loguru import logger
from contextlib import contextmanager
from alembic.util.exc import CommandError
from sqlmodel import Session

if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseService


def initialize_database():
    logger.debug("Initializing database")
    from langflow.services import service_manager, ServiceType

    database_service: "DatabaseService" = service_manager.get(
        ServiceType.DATABASE_SERVICE
    )
    try:
        database_service.create_db_and_tables()
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            logger.error(f"Error creating DB and tables: {exc}")
            raise RuntimeError("Error creating DB and tables") from exc
    try:
        database_service.check_schema_health()
    except Exception as exc:
        logger.error(f"Error checking schema health: {exc}")
        raise RuntimeError("Error checking schema health") from exc
    try:
        database_service.run_migrations()
    except CommandError as exc:
        if "Can't locate revision identified by" not in str(exc):
            raise exc
        # This means there's wrong revision in the DB
        # We need to delete the alembic_version table
        # and run the migrations again
        logger.warning(
            "Wrong revision in DB, deleting alembic_version table and running migrations again"
        )
        with session_getter(database_service) as session:
            session.execute("DROP TABLE alembic_version")
        database_service.run_migrations()
    except Exception as exc:
        # if the exception involves tables already existing
        # we can ignore it
        if "already exists" not in str(exc):
            logger.error(f"Error running migrations: {exc}")
            raise RuntimeError("Error running migrations") from exc
    logger.debug("Database initialized")


@contextmanager
def session_getter(db_service: "DatabaseService"):
    try:
        session = Session(db_service.engine)
        yield session
    except Exception as e:
        print("Session rollback because of exception:", e)
        session.rollback()
        raise
    finally:
        session.close()


@dataclass
class Result:
    name: str
    type: str
    success: bool


@dataclass
class TableResults:
    table_name: str
    results: list[Result]
