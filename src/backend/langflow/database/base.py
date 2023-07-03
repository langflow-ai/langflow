from langflow.settings import settings
from sqlmodel import SQLModel, Session, create_engine
from langflow.utils.logger import logger

if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables():
    logger.debug("Creating database and tables")
    SQLModel.metadata.create_all(engine)
    # Now check if the table Flow exists, if not, something went wrong
    # and we need to create the tables again.
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "flow" not in inspector.get_table_names():
        logger.error("Something went wrong creating the database and tables.")
        logger.error("Please check your database settings.")
        raise RuntimeError("Something went wrong creating the database and tables.")
    else:
        logger.debug("Database and tables created successfully")


def get_session():
    with Session(engine) as session:
        yield session
