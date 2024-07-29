from pathlib import Path
from typing import TYPE_CHECKING, List

from platformdirs import user_cache_dir

from langflow.services.base import Service
from langflow.services.monitor.utils import (
    new_duckdb_locked_connection,
)

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class MonitorService(Service):
    """
    Deprecated. Still connecting to duckdb to migrate old installations.
    """

    name = "monitor_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        self.base_cache_dir = Path(user_cache_dir("langflow"), ensure_exists=True)
        self.db_path = self.base_cache_dir / "monitor.duckdb"

    def exec_query(self, query: str, read_only: bool = False):
        with new_duckdb_locked_connection(self.db_path, read_only=read_only) as conn:
            return conn.execute(query).df()

    def get_messages(
        self,
        flow_id: str | None = None,
        sender: str | None = None,
        sender_name: str | None = None,
        session_id: str | None = None,
        order_by: str | None = "timestamp",
        order: str | None = "DESC",
        limit: int | None = None,
    ):
        query = "SELECT index, flow_id, sender_name, sender, session_id, text, files, timestamp FROM messages"
        conditions = []
        if sender:
            conditions.append(f"sender = '{sender}'")
        if sender_name:
            conditions.append(f"sender_name = '{sender_name}'")
        if session_id:
            conditions.append(f"session_id = '{session_id}'")
        if flow_id:
            conditions.append(f"flow_id = '{flow_id}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if order_by and order:
            # Make sure the order is from newest to oldest
            query += f" ORDER BY {order_by} {order.upper()}"

        if limit is not None:
            query += f" LIMIT {limit}"

        with new_duckdb_locked_connection(self.db_path, read_only=True) as conn:
            df = conn.execute(query).df()

        return df

    def delete_messages(self, message_ids: list[int] | str):
        if isinstance(message_ids, list):
            # If message_ids is a list, join the string representations of the integers
            ids_str = ",".join(map(str, message_ids))
        elif isinstance(message_ids, str):
            # If message_ids is already a string, use it directly
            ids_str = message_ids
        else:
            raise ValueError("message_ids must be a list of integers or a string")

        query = f"DELETE FROM messages WHERE index IN ({ids_str})"

        return self.exec_query(query, read_only=False)

    def get_transactions(self, limit: int = 100):
        query = f"SELECT index,flow_id, status, error, timestamp, vertex_id, inputs, outputs, target_id FROM transactions LIMIT {str(limit)}"
        with new_duckdb_locked_connection(self.db_path, read_only=True) as conn:
            df = conn.execute(query).df()

        return df.to_dict(orient="records")

    def delete_transactions(self, ids: List[int]) -> None:
        with new_duckdb_locked_connection(self.db_path, read_only=False) as conn:
            conn.execute(f"DELETE FROM transactions WHERE index in ({','.join(map(str, ids))})")
            conn.commit()
