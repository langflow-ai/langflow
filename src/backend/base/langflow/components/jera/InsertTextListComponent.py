from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, Output, TableInput
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class InsertTextListComponent(Component):
    display_name = "Insert Text List Component"
    description = "Insert a list of texts into a Milvus collection."
    icon = "special_components"
    name = "InsertTextListComponent"
    
    # Define the inputs for generate_schema
    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Database server host.", required=True),
        IntInput(name="port", display_name="Port", info="Server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Db Name", info="Database name.", required=False),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="Name of the new collection to be created.", required=True),
        TableInput(name="datas", display_name="Data", info="Data inserted.", required=True, table_schema=[{"name": "data", "formatter": "string", "display_name": "Data"}])
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Generated JSON Schema", name="json_schema", method="build_output"),
    ]
    
    def build_output(self) -> Data:
        dt = [row.get("data", "").strip() for row in self.datas if "data" in row]
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
        url = f"{SDCP_ROOT_URL}embedding/insert_text_list/"

        # Prepare the body
        fields = {
          "host": self.host,
          "port": self.port,
          "user": self.user,
          "password": self.password,
          "db_name": self.db_name,
          "collection_name": self.collection_name,
          "data": dt
        }

        response = http.request('POST', url, headers=headers, json=fields)
        
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result.get("result", ""))