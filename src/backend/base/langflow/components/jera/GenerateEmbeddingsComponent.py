from langflow.custom import Component
from langflow.io import Output, TableInput
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class GenerateEmbeddingsComponent(Component):
    display_name = "Generate Embeddings Component"
    description = "Generate embeddings for provided documents."
    icon = "special_components"
    name = "GenerateEmbeddingsComponent"
    
    # Define the inputs for generate_schema
    inputs = [
        TableInput(name="my_table", display_name="Documents", info="Documents to generate embeddings for.", required=True, table_schema=[{
            "name": "doc", 
            "display_name": "Text or Document"}]),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Generated JSON Schema", name="json_schema", method="build_output"),
    ]
    
    def build_output(self) -> Data:
        docs = [(row.get("doc") or "").strip() for row in self.my_table if "doc" in row]
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        url = f"http://{SDCP_ROOT_URL}/embedding/generate_embeddings/"
        fields = {"docs": docs}
        response = http.request('POST', url, headers=headers, json=fields)
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result.get("result", []))