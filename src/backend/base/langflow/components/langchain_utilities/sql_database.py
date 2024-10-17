from langchain_community.utilities.sql_database import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from langflow.io import (
    StrInput,
    Output,
)
from langflow.custom import Component


class SQLDatabaseComponent(Component):
    display_name = "SQLDatabase"
    description = "SQL Database"
    name = "SQLDatabase"

    inputs = [
        StrInput(name="uri", display_name="URI", info="URI to the database.", required=True),
    ]

    outputs = [
        Output(display_name="SQLDatabase", name="SQLDatabase", method="build_sqldatabase"),
    ]

    def clean_up_uri(self, uri: str) -> str:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://")
        return uri.strip()

    def build_sqldatabase(self) -> SQLDatabase:
        uri = self.clean_up_uri(self.uri)
        # Create an engine using SQLAlchemy with StaticPool
        engine = create_engine(uri, poolclass=StaticPool)
        return SQLDatabase(engine)
