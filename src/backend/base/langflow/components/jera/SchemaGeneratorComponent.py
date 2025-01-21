from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class SchemaGeneratorComponent(Component):
    display_name = "Schema Generator Component"
    description = "Generates a schema from a user query."
    icon = "database-zap"
    name = "SchemaGeneratorComponent"
    
    # Define the inputs for generate_schema
    inputs = [
        MessageTextInput(name="user_query", display_name="User Query", info="Enter the user query for schema generation.", required=True),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Generated JSON Schema", name="json_schema", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
        user_query = self.user_query
        
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        url = f"http://{SDCP_ROOT_URL}/diagram_extractor/generate_schema/"

        # Prepare the body
        body = {
            "user_query": user_query,
        }

        headers={'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        # Make the API request
        response = http.request(
            'POST',
            url,
            headers=headers,
            body=json.dumps(body)
        )
        
        result = json.loads(response.data.decode('utf-8'))
        json_schema = result.get("json_schema", {})
        return Data(value=json_schema)
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
