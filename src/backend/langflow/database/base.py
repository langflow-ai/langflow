from langflow.settings import settings
from sqlmodel import SQLModel, Session, create_engine


if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}
engine = create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
