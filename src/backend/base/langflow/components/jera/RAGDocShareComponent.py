from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, Output, NestedDictInput
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class RAGDocShareComponent(Component):
    display_name = "RAG DocShare Component"
    description = "searches the connected document store for relevant documents"
    icon = "special_components"
    name = "RAGDocShareComponent"
    
    # Define the inputs for generate_schema
    inputs = [
        MessageTextInput(name="host", display_name="Host", info="Database server host.", required=True),
        IntInput(name="port", display_name="Port", info="Server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Db Name", info="Database name.", required=False),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="Target collection for the deletion.", required=True),
        MessageTextInput(name="question", display_name="Question", info="The input query for which an answer is required.", required=True),
        MessageTextInput(name="requesting_agent", display_name="Requesting Agent", info="Identifier for the agent requesting the query.", required=True),
        NestedDictInput(name="langfuse_keys", display_name="Langfuse Keys", info="Keys for Langfuse integration.", required=False, value={}),
        NestedDictInput(name="langfuse_metadata", display_name="Langfuse Metadata", info="Metadata for Langfuse tracking.", required=False, value={}),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Generated JSON Schema", name="json_schema", method="build_output"),
    ]
    
    def build_output(self) -> Data:
        langfuse_keys = self.langfuse_keys if isinstance(self.langfuse_keys, dict) else {}
        langfuse_metadata = self.langfuse_metadata if isinstance(self.langfuse_metadata, dict) else {}

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
        url = f"{SDCP_ROOT_URL}docshare/rag/"

        # Prepare the body
        fields = {
          "host": self.host,
          "port": self.port,
          "user": self.user,
          "password": self.password,
          "db_name": self.db_name,
          "collection_name": self.collection_name,
          "question": self.question,
          "requesting_agent": self.requesting_agent,
          "langfuse_metadata": json.dumps(langfuse_keys),
          "langfuse_keys": json.dumps(langfuse_metadata)
        }

        response = http.request('POST', url, headers=headers, json=fields)
        
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result)