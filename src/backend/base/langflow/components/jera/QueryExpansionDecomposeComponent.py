from langflow.custom import Component
from langflow.io import Output, MessageTextInput, MultilineInput
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
 
 
class QueryExpansionDecomposeComponent(Component):
    display_name = "User Query expansion Decompose Component"
    description = "Use this component to expand your query."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "component"
    name = "QueryExpansionComponentDecompose"
 
    inputs = [
        MultilineInput(
            name="user_query",
            display_name="your Query",
            info="the user query",
        ),
        MessageTextInput(name="max_subqueries_number", display_name=" Max number of subqueries", info="the max nunber of subqueries"),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
 
    def build_output_data(self) -> Data:
        user_query = self.user_query
        max_subqueries_number = self.max_subqueries_number
       
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"http://{SDCP_ROOT_URL}/query_expansion/decompose/"

        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        # Prepare the fields for application/json
        fields = {
            'user_query': user_query,
            'max_subqueries_number': max_subqueries_number,
            'requesting_agent': "langflow",
            'langfuse_metadata': {},
            'langfuse_keys': {}
        }
        encoded_data = json.dumps(fields).encode('utf-8')

        response = http.request('POST', url, body=encoded_data, headers=headers)
        result = json.loads(response.data.decode('utf-8'))

        data_obj = Data(value=result["expanded_queries"])
       
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
 
 