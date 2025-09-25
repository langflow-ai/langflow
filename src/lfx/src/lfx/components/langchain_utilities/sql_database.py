from langchain_community.utilities.sql_database import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool, StaticPool

from lfx.custom.custom_component.component import Component
from lfx.io import (
    Output,
    StrInput,
)


class SQLDatabaseComponent(Component):
    display_name = "SQLDatabase"
    description = "SQL Database"
    name = "SQLDatabase"
    icon = "LangChain"

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
        url = make_url(uri)
        is_postgresql = url.get_backend_name() == "postgresql" or url.drivername.startswith("postgresql")

        # Choose appropriate pool class based on database type
        # For PostgreSQL, use NullPool to avoid keeping connections open
        # This closes the connection after each use instead of maintaining a pool
        # For SQLite and other databases, StaticPool is fine
        poolclass = NullPool if is_postgresql else StaticPool

        engine = create_engine(uri, poolclass=poolclass)
        return SQLDatabase(engine)
