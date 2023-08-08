from typing import TYPE_CHECKING
from langflow.utils.logger import logger
from contextlib import contextmanager

from sqlmodel import Session

if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseManager


def initialize_database():
    logger.debug("Initializing database")
    from langflow.services import service_manager, ServiceType

    database_manager = service_manager.get(ServiceType.DATABASE_MANAGER)
    database_manager.run_migrations()
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
