from json.decoder import JSONDecodeError

from google.auth.exceptions import RefreshError
from google.cloud import bigquery
from google.oauth2.service_account import Credentials

from langflow.custom import Component
from langflow.io import FileInput, MessageTextInput, Output
from langflow.schema.dataframe import DataFrame


class BigQueryExecutorComponent(Component):
    display_name = "BigQuery"
    description = "Execute SQL queries on Google BigQuery."
    name = "BigQueryExecutor"
    icon = "Google"
    beta: bool = True

    inputs = [
        FileInput(
            name="service_account_json_file",
            display_name="Upload Service Account JSON",
            info="Upload the JSON file containing Google Cloud service account credentials.",
            file_types=["json"],
            required=True,
        ),
        MessageTextInput(
            name="project_id",
            display_name="GCP Project ID",
            info="The Google Cloud Project ID associated with BigQuery.",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="SQL Query",
            info="he SQL query to execute on BigQuery.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Query Results", name="query_results", method="execute_sql"),
    ]

    def execute_sql(self) -> DataFrame:
        try:
            # service_account_json_file = service_account.Credentials.from_service_account_file(self.service_account_json_file)
            # file_content = JsonSpec.from_file(service_account_json_file)
            # credentials_info = json.loads(file_content)
            credentials = Credentials.from_service_account_file(self.service_account_json_file)
        except JSONDecodeError as e:
            msg = "Invalid JSON string for service account credentials."
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"Error loading service account credentials: {e}"
            raise ValueError(msg) from e

        try:
            client = bigquery.Client(credentials=credentials, project=self.project_id)
            sql_query = str(self.query)
            # sql_query = re.search(r"```sql\s*(.*?)\s*```", query_text, re.DOTALL)
            if sql_query:
                # sql_query = sql_query.group(1).strip()  # Extract only the SQL statement
                sql_query = sql_query.strip()
            else:
                msg = "No valid SQL query found in input text."
                raise ValueError(msg)  # Raise error if no SQL query is found
            # query_text = query_text.strip().replace("```", "").lstrip("sql")
            query_job = client.query(sql_query)
            results = query_job.result()
            output_dict = [dict(row) for row in results]
            # output = json.dumps(output_dict, indent=4, sort_keys=True, default=str)

        except RefreshError as e:
            msg = "Authentication error: Unable to refresh authentication token. Please try to reauthenticate."
            raise ValueError(msg) from e
        except Exception as e:
            msg = f"Error executing BigQuery SQL query: {e}"
            raise ValueError(msg) from e

        return DataFrame(output_dict)
