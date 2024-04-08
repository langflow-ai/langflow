from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

import duckdb
from loguru import logger
from platformdirs import user_cache_dir

from langflow.services.base import Service
from langflow.services.monitor.schema import MessageModel, TransactionModel, VertexBuildModel
from langflow.services.monitor.utils import add_row_to_table, drop_and_create_table_if_schema_mismatch

if TYPE_CHECKING:
    from langflow.services.settings.manager import SettingsService


class MonitorService(Service):
    name = "monitor_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        self.base_cache_dir = Path(user_cache_dir("langflow"))
        self.db_path = self.base_cache_dir / "monitor.duckdb"
        self.table_map = {
            "transactions": TransactionModel,
            "messages": MessageModel,
            "vertex_builds": VertexBuildModel,
        }

        try:
            self.ensure_tables_exist()
        except Exception as e:
            logger.exception(f"Error initializing monitor service: {e}")

    def to_df(self, table_name):
        return self.load_table_as_dataframe(table_name)

    def ensure_tables_exist(self):
        for table_name, model in self.table_map.items():
            drop_and_create_table_if_schema_mismatch(str(self.db_path), table_name, model)

    def add_row(
        self,
        table_name: str,
        data: Union[dict, TransactionModel, MessageModel, VertexBuildModel],
    ):
        # Make sure the model passed matches the table

        model = self.table_map.get(table_name)
        if model is None:
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

    def get_vertex_builds(
        self,
        flow_id: Optional[str] = None,
        vertex_id: Optional[str] = None,
        valid: Optional[bool] = None,
        order_by: Optional[str] = "timestamp",
    ):
        query = "SELECT id, flow_id, valid, params, data, artifacts, timestamp FROM vertex_builds"
        conditions = []
        if flow_id:
            conditions.append(f"flow_id = '{flow_id}'")
        if vertex_id:
            conditions.append(f"id = '{vertex_id}'")
        if valid is not None:  # Check for None because valid is a boolean
            valid_str = "true" if valid else "false"
            conditions.append(f"valid = {valid_str}")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if order_by:
            query += f" ORDER BY {order_by}"

        with duckdb.connect(str(self.db_path)) as conn:
            df = conn.execute(query).df()

        return df.to_dict(orient="records")

    def delete_vertex_builds(self, flow_id: Optional[str] = None):
        query = "DELETE FROM vertex_builds"
        if flow_id:
            query += f" WHERE flow_id = '{flow_id}'"

        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute(query)

    def delete_messages(self, session_id: str):
        query = f"DELETE FROM messages WHERE session_id = '{session_id}'"

        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute(query)

    def add_message(self, message: MessageModel):
        self.add_row("messages", message)

    def get_messages(
        self,
        sender: Optional[str] = None,
        sender_name: Optional[str] = None,
        session_id: Optional[str] = None,
        order_by: Optional[str] = "timestamp",
        order: Optional[str] = "DESC",
        limit: Optional[int] = None,
    ):
        query = "SELECT sender_name, sender, session_id, message, artifacts, timestamp FROM messages"
        conditions = []
        if sender:
            conditions.append(f"sender = '{sender}'")
        if sender_name:
            conditions.append(f"sender_name = '{sender_name}'")
        if session_id:
            conditions.append(f"session_id = '{session_id}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if order_by and order:
            # Make sure the order is from newest to oldest
            query += f" ORDER BY {order_by} {order.upper()}"

        if limit is not None:
            query += f" LIMIT {limit}"

        with duckdb.connect(str(self.db_path)) as conn:
            df = conn.execute(query).df()

        return df

    def get_transactions(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None,
        status: Optional[str] = None,
        order_by: Optional[str] = "timestamp",
    ):
        query = "SELECT source, target, target_args, status, error, timestamp FROM transactions"
        conditions = []
        if source:
            conditions.append(f"source = '{source}'")
        if target:
            conditions.append(f"target = '{target}'")
        if status:
            conditions.append(f"status = '{status}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if order_by:
            query += f" ORDER BY {order_by}"
        with duckdb.connect(str(self.db_path)) as conn:
            df = conn.execute(query).df()

        return df.to_dict(orient="records")
