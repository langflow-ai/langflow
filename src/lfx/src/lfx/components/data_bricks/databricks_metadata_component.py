import os

from databricks import sql
from dotenv import load_dotenv
from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data

# Load environment variables
load_dotenv()


class DataBricksMetadataComponent(Component):
    display_name = "DataBricks Metadata Scanner"
    description = "Scan DataBricks schemas and tables to retrieve metadata information including catalogs, schemas, tables, and columns."
    documentation: str = "https://docs.databricks.com/aws/en/dev-tools/python-sql-connector?language=SQL%C2%A0warehouse#query-metadata"
    icon = "DataBricks"
    name = "DataBricksMetadataScanner"

    inputs = [
        StrInput(
            name="server_hostname",
            display_name="Server Hostname",
            info="DataBricks server hostname (e.g., your-workspace.cloud.databricks.com)",
            required=True,
        ),
        StrInput(
            name="http_path",
            display_name="HTTP Path",
            info="DataBricks HTTP path for SQL endpoint",
            required=True
        ),
        SecretStrInput(
            name="access_token",
            display_name="Access Token",
            info="DataBricks personal access token",
            value=os.getenv("DATABRICKS_TOKEN", ""),
            required=True,
        ),
        MessageTextInput(
            name="catalog_name",
            display_name="Catalog Name",
            info="Optional catalog name to filter results. Leave empty to scan all catalogs.",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="schema_name",
            display_name="Schema Name",
            info="Optional schema name to filter results. Leave empty to scan all schemas.",
            value="",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Full Metadata", name="full_metadata", method="get_full_metadata"),
        Output(display_name="Table JSON Metadata", name="table_json_metadata", method="get_table_json_metadata"),
    ]

    def get_full_metadata(self) -> Data:
        """Get complete metadata including catalogs, schemas, tables, and columns."""
        try:
            metadata = {
                "catalogs": [],
                "schemas": [],
                "tables": [],
                "columns": []
            }

            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    # Get catalogs
                    try:
                        cursor.catalogs()
                        catalogs = cursor.fetchall()
                        for row in catalogs:
                            metadata["catalogs"].append({
                                "catalog_name": row[0] if len(row) > 0 else None,
                                "description": row[1] if len(row) > 1 else None
                            })
                    except Exception as e:
                        metadata["catalogs"] = [{"error": f"Failed to get catalogs: {e!s}"}]

                    # Get schemas
                    try:
                        if self.catalog_name:
                            cursor.schemas(catalog_name=self.catalog_name)
                        else:
                            cursor.schemas()
                        schemas = cursor.fetchall()
                        for row in schemas:
                            metadata["schemas"].append({
                                "catalog_name": row[0] if len(row) > 0 else None,
                                "schema_name": row[1] if len(row) > 1 else None,
                                "description": row[2] if len(row) > 2 else None
                            })
                    except Exception as e:
                        metadata["schemas"] = [{"error": f"Failed to get schemas: {e!s}"}]

                    # Get tables
                    try:
                        if self.catalog_name and self.schema_name:
                            cursor.tables(catalog_name=self.catalog_name, schema_name=self.schema_name)
                        elif self.catalog_name:
                            cursor.tables(catalog_name=self.catalog_name)
                        elif self.schema_name:
                            cursor.tables(schema_name=self.schema_name)
                        else:
                            cursor.tables()
                        tables = cursor.fetchall()
                        for row in tables:
                            metadata["tables"].append({
                                "catalog_name": row[0] if len(row) > 0 else None,
                                "schema_name": row[1] if len(row) > 1 else None,
                                "table_name": row[2] if len(row) > 2 else None,
                                "table_type": row[3] if len(row) > 3 else None,
                                "description": row[4] if len(row) > 4 else None
                            })
                    except Exception as e:
                        metadata["tables"] = [{"error": f"Failed to get tables: {e!s}"}]

                    # Get columns for first few tables (to avoid overwhelming output)
                    try:
                        table_count = 0
                        for table in metadata["tables"][:5]:  # Limit to first 5 tables
                            if "error" not in table:
                                catalog_name = table["catalog_name"]
                                schema_name = table["schema_name"]
                                table_name = table["table_name"]

                                try:
                                    cursor.columns(
                                        catalog_name=catalog_name,
                                        schema_name=schema_name,
                                        table_name=table_name
                                    )
                                    columns = cursor.fetchall()

                                    for col in columns:
                                        metadata["columns"].append({
                                            "catalog_name": col[0] if len(col) > 0 else None,
                                            "schema_name": col[1] if len(col) > 1 else None,
                                            "table_name": col[2] if len(col) > 2 else None,
                                            "column_name": col[3] if len(col) > 3 else None,
                                            "data_type": col[4] if len(col) > 4 else None,
                                            "nullable": col[5] if len(col) > 5 else None,
                                            "comment": col[6] if len(col) > 6 else None
                                        })
                                    table_count += 1
                                except Exception as col_err:
                                    metadata["columns"].append({
                                        "catalog_name": catalog_name,
                                        "schema_name": schema_name,
                                        "table_name": table_name,
                                        "column_name": None,
                                        "error": f"Failed to get columns: {e!s}"
                                    })
                                    continue
                    except Exception as e:
                        metadata["columns"] = [{"error": f"Failed to get columns: {e!s}"}]

            self.status = f"Retrieved metadata: {len(metadata['catalogs'])} catalogs, {len(metadata['schemas'])} schemas, {len(metadata['tables'])} tables, {len(metadata['columns'])} columns."
            return Data(value=metadata)

        except Exception as e:
            error_msg = f"Error retrieving full metadata: {e!s}"
            self.status = error_msg
            return Data(value={"error": error_msg})

    def get_table_json_metadata(self) -> Data:
        """Get detailed table metadata using DESCRIBE TABLE AS JSON for all tables in the specified catalog/schema."""
        try:
            table_json_metadata = {
                "catalog_name": self.catalog_name,
                "schema_name": self.schema_name,
                "tables": []
            }

            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    # First get all tables in the specified catalog/schema
                    try:
                        if self.catalog_name and self.schema_name:
                            cursor.tables(catalog_name=self.catalog_name, schema_name=self.schema_name)
                        elif self.catalog_name:
                            cursor.tables(catalog_name=self.catalog_name)
                        elif self.schema_name:
                            cursor.tables(schema_name=self.schema_name)
                        else:
                            cursor.tables()
                        tables = cursor.fetchall()

                        # Get JSON metadata for each table
                        for table in tables:
                            catalog_name = table[0]
                            schema_name = table[1]
                            table_name = table[2]

                            try:
                                # Use DESCRIBE TABLE AS JSON for detailed metadata
                                cursor.execute(f"DESCRIBE TABLE `{catalog_name}`.`{schema_name}`.`{table_name}` AS JSON")
                                json_result = cursor.fetchall()

                                # Parse the JSON result
                                table_metadata = {
                                    "catalog_name": catalog_name,
                                    "schema_name": schema_name,
                                    "table_name": table_name,
                                    "table_type": table[3] if len(table) > 3 else None,
                                    "description": table[4] if len(table) > 4 else None,
                                    "json_metadata": json_result[0][0] if json_result and len(json_result) > 0 else None,
                                    "error": None
                                }

                                table_json_metadata["tables"].append(table_metadata)

                            except Exception as e:
                                # If DESCRIBE TABLE AS JSON fails, try regular DESCRIBE
                                try:
                                    cursor.execute(f"DESCRIBE TABLE {catalog_name}.{schema_name}.{table_name}")
                                    describe_result = cursor.fetchall()

                                    table_metadata = {
                                        "catalog_name": catalog_name,
                                        "schema_name": schema_name,
                                        "table_name": table_name,
                                        "table_type": table[3] if len(table) > 3 else None,
                                        "description": table[4] if len(table) > 4 else None,
                                        "json_metadata": None,
                                        "describe_metadata": [list(row) for row in describe_result],
                                        "error": f"DESCRIBE TABLE AS JSON failed: {e!s}"
                                    }

                                    table_json_metadata["tables"].append(table_metadata)

                                except Exception as e2:
                                    table_metadata = {
                                        "catalog_name": catalog_name,
                                        "schema_name": schema_name,
                                        "table_name": table_name,
                                        "table_type": table[3] if len(table) > 3 else None,
                                        "description": table[4] if len(table) > 4 else None,
                                        "json_metadata": None,
                                        "describe_metadata": None,
                                        "error": f"Both DESCRIBE methods failed: {e!s} | {e2!s}"
                                    }

                                    table_json_metadata["tables"].append(table_metadata)

                        self.status = f"Retrieved JSON metadata for {len(table_json_metadata['tables'])} tables"
                        return Data(value=table_json_metadata)

                    except Exception as e:
                        error_msg = f"Error getting table list: {e!s}"
                        self.status = error_msg
                        return Data(value={"error": error_msg})

        except Exception as e:
            error_msg = f"Error retrieving table JSON metadata: {e!s}"
            self.status = error_msg
            return Data(value={"error": error_msg})
