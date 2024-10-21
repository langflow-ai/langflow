from langchain_community.utilities.sql_database import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from langflow.custom import CustomComponent


class SQLDatabaseComponent(CustomComponent):
    display_name = "SQLDatabase"
    description = "SQL Database"
    name = "SQLDatabase"

    def build_config(self):
        return {
            "uri": {"display_name": "URI", "info": "URI to the database."},
        }

    def clean_up_uri(self, uri: str) -> str:
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://")
        return uri.strip()

    def build(self, uri: str) -> SQLDatabase:
        uri = self.clean_up_uri(uri)
        # Create an engine using SQLAlchemy with StaticPool
        engine = create_engine(uri, poolclass=StaticPool)
        return SQLDatabase(engine)
