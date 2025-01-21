from langflow.custom import Component
from langflow.io import MessageTextInput, TableInput, NestedDictInput, IntInput, Output
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class CreateCustomCollectionComponent(Component):
    display_name = "Create Custom Collection Component"
    description = "Create a custom collection with specific attributes."
    icon = "special_components"
    name = "CreateCustomCollectionComponent"
    
    # Define the inputs for generate_schema
    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Database server host.", required=True),
        IntInput(name="port", display_name="Port", info="Server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Db Name", info="Database name where the collection is to be created.", required=True),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="Name of the collection to be created.", required=True),
        MessageTextInput(name="dscrpt", display_name="Description", info="A brief description of the collection.", required=False),
        TableInput(name="input_fields", display_name="Fields", info="Defines the fields in the collection with details such as data type, primary key status, and other attributes.", required=True, table_schema=[{"name":"name"},{"name":"dtype"},{"name": "is_primary"},{"name": "auto_id"},{"name": "max_length"},{"name": "dim"},{"name": "description"}]),
        MessageTextInput(name="index_field_name", display_name="Index Field Name", info="The primary field used for indexing.", required=True),
        NestedDictInput(name="index_params", display_name="Index Params", info="Parameters used for configuring the index.", required=False),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Generated JSON Schema", name="json_schema", method="build_output"),
    ]
    
    def build_output(self) -> Data:
        processed_table = []
        for row in self.input_fields:
            processed_row = {
                "name": row.get("name") or "",
                "dtype": row.get("dtype") or "",
                "is_primary": str(row.get("is_primary") or True).lower() == "true",
                "auto_id": str(row.get("auto_id") or True).lower() == "true",
                "max_length": int(row.get("max_length") or 0),
                "dim": int(row.get("dim") or 0),
                "description": row.get("description") or "",
            }
            processed_table.append(processed_row)
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        url = f"http://{SDCP_ROOT_URL}/embedding/create_custom_collection/"

        # Prepare the body
        fields = {
          "host": self.host,
          "port": self.port,
          "user": self.user,
          "password": self.password,
          "db_name": self.db_name,
          "collection_name": self.collection_name,
          "description": self.dscrpt,
          "fields": processed_table,
          "index_field_name": self.index_field_name,
          "index_params": json.dumps(self.index_params)
        }

        response = http.request('POST', url, headers=headers, json=fields)
        
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result.get("result", ""))