from langflow.custom import Component
from langflow.io import MessageTextInput, NestedDictInput, IntInput, Output, TableInput
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class CustomCollectionSearchComponent(Component):
    display_name = "Custom Collection Search Component"
    description = "Perform a custom search on a Milvus collection."
    icon = "special_components"
    name = "CustomCollectionSearchComponent"
    
    # Define the inputs for generate_schema
    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Database server host.", required=True),
        IntInput(name="port", display_name="Port", info="Server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Db Name", info="Database name.", required=False),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="Target collection for the deletion.", required=True),
        MessageTextInput(name="query", display_name="Query", info="Text query for the search.", required=True),
        IntInput(name="limit", display_name="Limit", info="Maximum number of results to return.", required=True, value=3),
        MessageTextInput(name="embedding_model_name", display_name="Embedding Model Name", info="The name of the embedding model used for search.", required=True),
        MessageTextInput(name="anns_field", display_name="Anns Field", info="Specifies the field used for approximate nearest neighbor search.", required=True),
        NestedDictInput(name="param", display_name="Param", info="Additional parameters for fine-tuning the search.", required=False, value={}),
        TableInput(name="output_fields", display_name="Output Fields", info="Specifies which fields to include in the search results.", required=False, table_schema=[{"name": "fields", "formatter": "string", "display_name": "Output Fields"}]),

    ]
    
    # Define the output
    outputs = [
        Output(display_name="Generated JSON Schema", name="json_schema", method="build_output"),
    ]
    
    def build_output(self) -> Data:
        optfld = [row.get("fields", "").strip() for row in self.output_fields if "fields" in row]
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        url = f"{SDCP_ROOT_URL}embedding/custom_collection_search/"

        # Prepare the body
        fields = {
          "host": self.host,
          "port": self.port,
          "user": self.user,
          "password": self.password,
          "db_name": self.db_name,
          "collection_name": self.collection_name,
          "query": self.query,
          "limit": self.limit,
          "embedding_model_name": self.embedding_model_name,
          "anns_field": self.anns_field,
          "param": json.dumps(self.param),
          "output_fields": optfld
        }

        response = http.request('POST', url, headers=headers, json=fields)
        
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result.get("result", []))