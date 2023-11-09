import duckdb
from pydantic import BaseModel
from typing import Any, Dict, Type


def get_table_schema_as_dict(conn: duckdb.DuckDBPyConnection, table_name: str) -> dict:
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {row[1]: row[2].upper() for row in result}


def model_to_sql_column_definitions(model: Type[BaseModel]) -> dict:
    columns = {}
    for field_name, field_type in model.__fields__.items():
        field_info = field_type.type_
        if field_info.__name__ == "int":
            sql_type = "INTEGER"
        elif field_info.__name__ == "str":
            sql_type = "VARCHAR"
        elif field_info.__name__ == "datetime":
            sql_type = "TIMESTAMP"
        elif field_info.__name__ == "bool":
            sql_type = "BOOLEAN"
        elif field_info.__name__ == "dict":
            sql_type = "JSON"
        else:
            continue  # Skip types we don't handle
        columns[field_name] = sql_type
    return columns


def drop_and_create_table_if_schema_mismatch(
    db_path: str, table_name: str, model: Type[BaseModel]
):
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
                desired_schema[
                    "id"
                ] = f"INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_{table_name}')"
            columns_sql = ", ".join(
                f"{name} {data_type}" for name, data_type in desired_schema.items()
            )
            create_table_sql = f"CREATE TABLE {table_name} ({columns_sql})"
            conn.execute(create_table_sql)


def add_row_to_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    model: Type[BaseModel],
    monitor_data: Dict[str, Any],
):
    # Validate the data with the Pydantic model
    validated_data = model(**monitor_data)

    # Extract data for the insert statement
    validated_dict = validated_data.dict(exclude_unset=True)
    keys = [key for key in validated_dict.keys() if key != "id"]
    columns = ", ".join(keys)

    values_placeholders = ", ".join(["?" for _ in keys])
    values = list(validated_dict.values())

    # Create the insert statement
    insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({values_placeholders})"

    # Execute the insert statement
    conn.execute(insert_sql, values)
