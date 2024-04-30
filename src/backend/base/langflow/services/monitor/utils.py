from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

import duckdb
from loguru import logger
from pydantic import BaseModel

from langflow.services.deps import get_monitor_service

if TYPE_CHECKING:
    from langflow.api.v1.schemas import ResultDataResponse


INDEX_KEY = "index"


def get_table_schema_as_dict(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict:
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    schema = {row[1]: row[2].upper() for row in result}
    schema.pop(INDEX_KEY, None)
    return schema


def model_to_sql_column_definitions(model: Type[BaseModel]) -> dict:
    columns = {}
    for field_name, field_type in model.model_fields.items():
        if hasattr(field_type.annotation, "__args__") and field_type.annotation is not None:
            field_args = field_type.annotation.__args__
        else:
            field_args = []
        field_info = field_args[0] if field_args else field_type.annotation
        if field_info.__name__ == "int":
            sql_type = "INTEGER"
        elif field_info.__name__ == "str":
            sql_type = "VARCHAR"
        elif field_info.__name__ == "datetime":
            sql_type = "TIMESTAMP"
        elif field_info.__name__ == "bool":
            sql_type = "BOOLEAN"
        elif field_info.__name__ == "dict":
            sql_type = "VARCHAR"
        elif field_info.__name__ == "Any":
            sql_type = "VARCHAR"
        else:
            continue  # Skip types we don't handle
        columns[field_name] = sql_type
    return columns


def drop_and_create_table_if_schema_mismatch(db_path: str, table_name: str, model: Type[BaseModel]):
    with duckdb.connect(db_path) as conn:
        # Get the current schema from the database
        try:
            current_schema = get_table_schema_as_dict(conn, table_name)
        except duckdb.CatalogException:
            current_schema = {}
        # Get the desired schema from the model
        desired_schema = model_to_sql_column_definitions(model)

        # Compare the current and desired schemas

        if current_schema != desired_schema:
            # If they don't match, drop the existing table and create a new one
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            if "id" in desired_schema.keys():
                # Create a sequence for the id column
                try:
                    conn.execute(f"CREATE SEQUENCE seq_{table_name} START 1;")
                except duckdb.CatalogException:
                    pass
                desired_schema[INDEX_KEY] = f"INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_{table_name}')"
            columns_sql = ", ".join(f"{name} {data_type}" for name, data_type in desired_schema.items())
            create_table_sql = f"CREATE TABLE {table_name} ({columns_sql})"
            conn.execute(create_table_sql)


def add_row_to_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    model: Type,
    monitor_data: Union[Dict[str, Any], BaseModel],
):
    # Validate the data with the Pydantic model
    if isinstance(monitor_data, model):
        validated_data = monitor_data
    else:
        validated_data = model(**monitor_data)

    # Extract data for the insert statement
    validated_dict = validated_data.model_dump()
    keys = [key for key in validated_dict.keys() if key != INDEX_KEY]
    columns = ", ".join(keys)

    values_placeholders = ", ".join(["?" for _ in keys])
    values = list(validated_dict.values())

    # Create the insert statement
    insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({values_placeholders})"

    # Execute the insert statement
    try:
        conn.execute(insert_sql, values)
    except Exception as e:
        # Log values types
        column_error_message = ""
        for key, value in validated_dict.items():
            logger.error(f"{key}: {type(value)}")
            if value in str(e):
                column_error_message = f"Column: {key} Value: {value} Error: {e}"

        if column_error_message:
            logger.error(f"Error adding row to {table_name}: {column_error_message}")
        else:
            logger.error(f"Error adding row to {table_name}: {e}")


async def log_message(
    sender: str,
    sender_name: str,
    message: str,
    session_id: str,
    artifacts: Optional[dict] = None,
):
    try:
        from langflow.graph.vertex.base import Vertex

        if isinstance(session_id, Vertex):
            session_id = await session_id.build()  # type: ignore

        monitor_service = get_monitor_service()
        row = {
            "sender": sender,
            "sender_name": sender_name,
            "message": message,
            "artifacts": artifacts or {},
            "session_id": session_id,
            "timestamp": monitor_service.get_timestamp(),
        }
        monitor_service.add_row(table_name="messages", data=row)
    except Exception as e:
        logger.error(f"Error logging message: {e}")


async def log_vertex_build(
    flow_id: str,
    vertex_id: str,
    valid: bool,
    params: Any,
    data: "ResultDataResponse",
    artifacts: Optional[dict] = None,
):
    try:
        monitor_service = get_monitor_service()

        row = {
            "flow_id": flow_id,
            "id": vertex_id,
            "valid": valid,
            "params": params,
            "data": data.model_dump(),
            "artifacts": artifacts or {},
            "timestamp": monitor_service.get_timestamp(),
        }
        monitor_service.add_row(table_name="vertex_builds", data=row)
    except Exception as e:
        logger.exception(f"Error logging vertex build: {e}")
