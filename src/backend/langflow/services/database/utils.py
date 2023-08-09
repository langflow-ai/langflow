from typing import TYPE_CHECKING
from langflow.utils.logger import logger
from contextlib import contextmanager
from alembic.util.exc import CommandError
from sqlmodel import Session

if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseManager


def initialize_database():
    logger.debug("Initializing database")
    from langflow.services import service_manager, ServiceType

    database_manager = service_manager.get(ServiceType.DATABASE_MANAGER)
    try:
        database_manager.run_migrations()
    except CommandError as exc:
        if "Can't locate revision identified by" not in str(exc):
            raise exc
        # This means there's wrong revision in the DB
        # We need to delete the alembic_version table
        # and run the migrations again
        logger.warning(
            "Wrong revision in DB, deleting alembic_version table and running migrations again"
        )
        with session_getter(database_manager) as session:
            session.execute("DROP TABLE alembic_version")
        database_manager.run_migrations()
    except Exception as exc:
        logger.error(f"Error running migrations: {exc}")
        raise RuntimeError("Error running migrations") from exc
    database_manager.create_db_and_tables()
    logger.debug("Database initialized")


@contextmanager
def session_getter(db_manager: "DatabaseManager"):
    try:
        session = Session(db_manager.engine)
        yield session
    except Exception as e:
        print("Session rollback because of exception:", e)
        session.rollback()
        raise
    finally:
        session.close()
