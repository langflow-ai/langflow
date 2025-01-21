from langflow.custom import Component
from langflow.io import Output, MessageTextInput, MultilineInput
from langflow.schema import Data

import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from urllib.parse import urlencode
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")
 
 
class ImageURLtoTextComponent(Component):
    display_name = "Image URL to Text Component"
    description = "Use this component to extract information from image urls."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "file-symlink"
    name = "ImageUrltoTextComponent"
 
    inputs = [
        MultilineInput(
            name="URL_list",
            display_name="images URLs",
            info="comma seperated images URLs list",
        ),
        MessageTextInput(name="gpt_model_name", display_name="gpt model name", info="write the openai GPT model"),
        MultilineInput(
            name="prompt",
            display_name="Prompt to be passed to LLM",
            info="ask the LLM something about your image",
        ),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
 
    def build_output_data(self) -> Data:
        image_urls = self.URL_list
        gpt_model = self.gpt_model_name
        prompt = self.prompt
       
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"http://{SDCP_ROOT_URL}/image_processor/image_url_to_text/"
        
        headers = {'accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        # Prepare the fields for application/x-www-form-urlencoded
        fields = {
            'image_urls': image_urls,
            'gpt_model_name': gpt_model,
            'prompt': prompt
        }
        encoded_data = urlencode(fields)

        response = http.request('POST', url, body=encoded_data, headers=headers)
        result = json.loads(response.data.decode('utf-8'))

        data_obj = Data(value=result["result"])
       
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
 
 