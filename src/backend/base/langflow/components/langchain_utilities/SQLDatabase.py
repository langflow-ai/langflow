from langchain_community.utilities.sql_database import SQLDatabase
from langflow.custom import CustomComponent
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

class SQLDatabaseComponent(CustomComponent):
    display_name = "SQLDatabase"
    description = "SQL Database"
    name = "SQLDatabase"

    def build_config(self):
        return {
            "uri": {"display_name": "URI", "info": "URI to the database."},
        }

    def build(self, uri: str) -> SQLDatabase:
        # Create an engine using SQLAlchemy with StaticPool
        engine = create_engine(uri, poolclass=StaticPool)
        return SQLDatabase(engine)
