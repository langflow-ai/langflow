import os

from databricks import sql
from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data


class DataBricksSchemaAnalyzer(Component):
    display_name = "DataBricks Schema Analyzer"
    description = "Analyze a specific DataBricks schema to get detailed information about all tables including schema summary, table summaries, and column details."
    documentation: str = "https://docs.databricks.com/aws/en/dev-tools/python-sql-connector?language=SQL%C2%A0warehouse#query-metadata"
    icon = "DataBricks"
    name = "DataBricksSchemaAnalyzer"

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
            required=True,
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
            info="Catalog name to analyze (e.g., 'samples')",
            value="samples",
            tool_mode=True,
        ),
        MessageTextInput(
            name="schema_name",
            display_name="Schema Name",
            info="Schema name to analyze (e.g., 'nyctaxi')",
            value="nyctaxi",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Complete Analysis", name="complete_analysis", method="get_complete_analysis"),
    ]


    def get_complete_analysis(self) -> Data:
        """Get complete analysis using DESCRIBE TABLE EXTENDED for all tables in the schema."""
        try:
            complete_analysis = {
                "catalog_name": self.catalog_name,
                "schema_name": self.schema_name,
                "schema_summary": {},
                "tables": [],
                "errors": []
            }

            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    # Get schema summary
                    try:
                        cursor.schemas(catalog_name=self.catalog_name)
                        schemas = cursor.fetchall()

                        target_schema = None
                        for schema in schemas:
                            if schema[1] == self.schema_name:
                                target_schema = {
                                    "catalog_name": schema[0],
                                    "schema_name": schema[1],
                                    "description": schema[2] if len(schema) > 2 else None
                                }
                                break

                        if target_schema:
                            complete_analysis["schema_summary"] = target_schema
                        else:
                            complete_analysis["errors"].append(f"Schema '{self.schema_name}' not found")

                    except Exception as e:
                        complete_analysis["errors"].append(f"Error getting schema info: {e!s}")

                    # Get tables and their extended metadata
                    try:
                        cursor.tables(catalog_name=self.catalog_name, schema_name=self.schema_name)
                        tables = cursor.fetchall()

                        complete_analysis["schema_summary"]["total_tables"] = len(tables)

                        # Get extended metadata for each table
                        for table in tables:
                            catalog_name = table[0]
                            schema_name = table[1]
                            table_name = table[2]

                            table_info = {
                                "catalog_name": catalog_name,
                                "schema_name": schema_name,
                                "table_name": table_name,
                                "table_type": table[3] if len(table) > 3 else "UNKNOWN",
                                "description": table[4] if len(table) > 4 else None,
                                "extended_metadata": None,
                                "error": None
                            }

                            # Get extended metadata using DESCRIBE TABLE EXTENDED
                            try:
                                cursor.execute(f"DESCRIBE TABLE EXTENDED `{catalog_name}`.`{schema_name}`.`{table_name}`")
                                extended_result = cursor.fetchall()

                                # Parse the extended metadata
                                extended_metadata = {}
                                for row in extended_result:
                                    if len(row) >= 2:
                                        key = row[0]
                                        value = row[1] if len(row) > 1 else None
                                        extended_metadata[key] = value

                                table_info["extended_metadata"] = extended_metadata

                            except Exception as e:
                                table_info["error"] = f"DESCRIBE TABLE EXTENDED failed: {e!s}"

                            complete_analysis["tables"].append(table_info)

                    except Exception as e:
                        complete_analysis["errors"].append(f"Error getting tables: {e!s}")

            self.status = f"Complete analysis for schema '{self.schema_name}' with {len(complete_analysis['tables'])} tables using DESCRIBE TABLE EXTENDED"
            return Data(value=complete_analysis)

        except Exception as e:
            error_msg = f"Error getting complete analysis: {e!s}"
            self.status = error_msg
            return Data(value={"error": error_msg})

