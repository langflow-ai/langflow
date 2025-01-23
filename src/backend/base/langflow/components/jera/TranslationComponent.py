from langflow.custom import Component
from langflow.io import DataInput, MessageTextInput, Output
from langflow.schema import Data
import json
 
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")
 
 
class TranslationComponent(Component):
    display_name = "Translation Component"
    description = "Use this component to translate text."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "TranslationComponent"
 
    inputs = [
        DataInput(name="data_input", display_name="Data", info="The data to convert to text."),
         MessageTextInput(
            name="translation_language",
            display_name="Translation language",
            info="The language to translate to",
            required=True
        ),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]
 
   
    def build_output(self) -> Data:
        text_to_translate = self.data_input.value if isinstance(self.data_input, Data) else {}
       
        translation_language = self.translation_language
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
 
        url = f"{SDCP_ROOT_URL}translate/"
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
 
        fields = json.dumps({
            "text": f"please translate the following text to {translation_language}: {text_to_translate}!",
            "requesting_agent": "SYM",
            "langfuse_metadata": {},
            "langfuse_keys": {}
        }).encode('utf-8')  # Encode to bytes
 
        response = http.request('POST', url, headers=headers, body=fields)
        response_data = json.loads(response.data.decode('utf-8'))
 
        # Extract the translated text
        translated_text = response_data["translated_text"]
 
        data_obj = Data(value=translated_text)
        return data_obj
 
 