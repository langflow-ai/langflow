from langflow.custom import Component
from langflow.io import Output, FileInput, MultilineInput
from langflow.schema import Data

import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from urllib3.filepost import encode_multipart_formdata
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")
 
 
class ImageFiletoTextComponent(Component):
    display_name = "Image File to Text Component"
    description = "Use this component to extract information from image files."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "image-down"
    name = "ImageFiletoTextComponent"
 
    inputs = [
        FileInput(name="image_file_path", display_name="Image File Path", file_types=["jpg", "jpeg", "png", "apng","bmp", "image", "jfif", "avif", "gif", "pjpeg", "pjp", "svg", "webp"], required=True),
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
        with open(self.image_file_path, 'rb') as file:
            file_content = file.read()
            prompt = self.prompt
           
            http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
 
            url = f"{SDCP_ROOT_URL}image_processor/image_file_to_text/"
            
            headers = {'accept': 'multipart/form-data'}
            if SDCP_TOKEN:
                headers['apikey'] = SDCP_TOKEN
 
            # Prepare the fields for multipart/form-data
            fields = {
                'image_file': ('images.jfif', file_content, 'image/jpeg'),
                'prompt': prompt
            }
            encoded_data, content_type = encode_multipart_formdata(fields)
            headers['Content-Type'] = content_type

            response = http.request('POST', url, body=encoded_data, headers=headers)
            result = json.loads(response.data.decode('utf-8'))
 
            data_obj = Data(value=result["result"])
           
            self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
 
 