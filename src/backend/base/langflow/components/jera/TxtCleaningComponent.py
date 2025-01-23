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


class TxtCleaningComponent(Component):
    display_name = "Txt Cleaning Component"
    description = "Use this component to clean text documents."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "shield-check"
    name = "TxtCleaningComponent"
    
    inputs = [
        MessageTextInput(name="docs", display_name="Documents", info="The input text document(s) to be cleaned.", required=True),
        MessageTextInput(name="stopwords", display_name="Stopwords", info="Enter stopwords separated by commas.", required=False),
        MessageTextInput(name="token_lower", display_name="Minimum Token Count", info="Minimum token count threshold.", required=False),
        MessageTextInput(name="to_lower", display_name="Convert to Lowercase", info="Convert text to lowercase (True/False).", required=False),
        MessageTextInput(name="remove_url", display_name="Remove URLs", info="Remove URLs from text (True/False).", required=False),
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
        input_docs = self.docs
        stopwords = [word.strip() for word in self.stopwords.split(',')] if self.stopwords else []
        token_lower = int(self.token_lower) if self.token_lower and self.token_lower.isdigit() else 0
        to_lower = self.to_lower.lower() == "true" if self.to_lower else True
        remove_url = self.remove_url.lower() == "true" if self.remove_url else True

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        base_url = f"{SDCP_ROOT_URL}data_cleaning/txt_cleaning/"

        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        query_params = []
        if stopwords:
            for word in stopwords:
                query_params.append(f"stopwords={word}")
        query_params.append(f"token_lower={token_lower}")
        query_params.append(f"to_lower={to_lower}")
        query_params.append(f"remove_url={remove_url}")
        url = f"{base_url}?{'&'.join(query_params)}"
        response = http.request(
            'POST',
            url,
            headers=headers,
            json=input_docs
        )
        
        result = json.loads(response.data.decode('utf-8'))
        cleaned_docs = result.get("docs", [])
        data_obj = Data(value=f"Cleaned Documents: {cleaned_docs}")
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
