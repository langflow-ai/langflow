from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Type, Union

import duckdb
from loguru import logger
from pydantic import BaseModel

from langflow.utils.concurrency import KeyedWorkerLockManager

if TYPE_CHECKING:
    pass


INDEX_KEY = "index"
worker_lock_manager = KeyedWorkerLockManager()


def get_table_schema_as_dict(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict:
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    schema = {row[1]: row[2].upper() for row in result}
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
    with new_duckdb_locked_connection(db_path) as conn:
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
            logger.warning(f"Schema mismatch for duckdb table {table_name}. Dropping and recreating table.")
            logger.debug(f"Current schema: {str(current_schema)}")
            logger.debug(f"Desired schema: {str(desired_schema)}")
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            if INDEX_KEY in desired_schema.keys():
                # Create a sequence for the id column
                try:
                    conn.execute(f"CREATE SEQUENCE seq_{table_name} START 1;")
                except duckdb.CatalogException:
                    pass
                desired_schema[INDEX_KEY] = f"INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_{table_name}')"
            columns_sql = ", ".join(f"{name} {data_type}" for name, data_type in desired_schema.items())
            create_table_sql = f"CREATE TABLE {table_name} ({columns_sql})"
            conn.execute(create_table_sql)


@contextmanager
def new_duckdb_locked_connection(db_path: Union[str, Path], read_only=False):
    with worker_lock_manager.lock("duckdb"):
        with duckdb.connect(str(db_path), read_only=read_only) as conn:
            yield conn


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
    values = [validated_dict[key] for key in keys]

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
            if str(value) in str(e):
                column_error_message = f"Column: {key} Value: {value} Error: {e}"

        if column_error_message:
            logger.error(f"Error adding row to {table_name}: {column_error_message}")
        else:
            logger.error(f"Error adding row to {table_name}: {e}")
