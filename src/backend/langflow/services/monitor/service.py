from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
from langflow.services.base import Service
from langflow.services.monitor.schema import MessageModel, TransactionModel
from langflow.services.monitor.utils import add_row_to_table, drop_and_create_table_if_schema_mismatch
from loguru import logger
from platformdirs import user_cache_dir

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsService


class MonitorService(Service):
    name = "monitor_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        self.base_cache_dir = Path(user_cache_dir("langflow"))
        self.db_path = self.base_cache_dir / "monitor.duckdb"
        try:
            self.ensure_tables_exist()
        except Exception as e:
            logger.error(f"Error initializing monitor service: {e}")

    def to_df(self, table_name):
        return self.load_table_as_dataframe(table_name)

    def ensure_tables_exist(self):
        drop_and_create_table_if_schema_mismatch(str(self.db_path), "transactions", TransactionModel)
        drop_and_create_table_if_schema_mismatch(str(self.db_path), "messages", MessageModel)

    def add_row(self, table_name: str, data: dict):
        # Make sure the model passed matches the table
        if table_name == "transactions":
            model = TransactionModel
        elif table_name == "messages":
            model = MessageModel
        else:
            raise ValueError(f"Unknown table name: {table_name}")

        # Connect to DuckDB and add the row
        with duckdb.connect(str(self.db_path)) as conn:
            add_row_to_table(conn, table_name, model, data)

    def load_table_as_dataframe(self, table_name):
        with duckdb.connect(str(self.db_path)) as conn:
            return conn.table(table_name).df()

    @staticmethod
    def get_timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
