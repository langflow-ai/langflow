from langflow.custom import Component
from langflow.io import Output, MessageTextInput
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class SimpleWebSearchComponent(Component):
    display_name = "Simple Web Search Component"
    description = "Use this component to generate a simple web search."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "SimpleWebSearchComponent"
    inputs = [
        MessageTextInput(name="query", display_name="Query", info="The query that will be searched", required=True),
        MessageTextInput(name="language", display_name="Language", info="The language of the result", required=False, value=""),
        MessageTextInput(name="safesearch", display_name="Safe Search", info="safe search of th query", required=False, value="moderate"),
        MessageTextInput(name="max_results", display_name="Max Results", info="max results displayed for the query", required=False, value="5"),
        MessageTextInput(name="requesting_agent", display_name="Requesting Agent", info="The requesting agent identifier", required=False, value="SYM"),
        # MessageTextInput(name="langfuse_metadata", display_name="Langfuse Metadata", info="User customized metadata that needs to be traced", required=False, value={}),
        # MessageTextInput(name="langfuse_keys", display_name="Langfuse Keys", info="Langfuse public and secret key", required=False, value={}),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}web_research/simple-search/"
        
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        fields = {
            "query" : self.query,
            "language": self.language,
            "safesearch": self.safesearch,
            "max_results": int(self.max_results),
            "requesting_agent":self.requesting_agent,
            "langfuse_metadata": {},
            "langfuse_keys": {}
        }
        response = http.request('POST', url, headers=headers, json=fields)
        result = json.loads(response.data.decode('utf-8'))
        data_obj = Data(value=result)
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)