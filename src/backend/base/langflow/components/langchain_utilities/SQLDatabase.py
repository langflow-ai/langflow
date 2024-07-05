from langchain_experimental.sql.base import SQLDatabase

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
        if uri.startswith("postgresql://"):
            uri = uri.replace("postgresql://", "postgres://")
        return uri.strip()

    def build(self, uri: str) -> SQLDatabase:
        uri = self.clean_up_uri(uri)
        return SQLDatabase.from_uri(uri)
