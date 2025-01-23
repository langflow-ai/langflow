from langflow.custom import Component
from langflow.io import Output, MultilineInput, DropdownInput
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
 
 
class TokenizerComponent(Component):
    display_name = "Tokenizer Component"
    description = "Use this component to tokenize your text."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "TokenizerComponent"
 
    inputs = [
        MultilineInput(
            name="text",
            display_name="your text",
            info="the user text",
        ),
        DropdownInput(name="tokenizer_method",
            display_name="tokenizer method",
            options=["sudachipy", "spacy"],
            value="sudachipy",
            info="The method that is used to tokenize the text",),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
 
    def build_output_data(self) -> Data:
        text = self.text
        tokenizer_method = self.tokenizer_method
       
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}tokenizer/{tokenizer_method}/"
        
        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        # Prepare the fields for application/json
        fields = [text]
        encoded_data = json.dumps(fields).encode('utf-8')

        response = http.request('POST', url, body=encoded_data, headers=headers)
        result = json.loads(response.data.decode('utf-8'))

        data_obj = Data(value=result["token_list"])
       
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
 
 