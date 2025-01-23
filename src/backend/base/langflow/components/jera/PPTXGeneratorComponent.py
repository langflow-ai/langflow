import os
import tempfile
from langflow.custom import Component
from langflow.io import Output, MessageTextInput
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
import time
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class PPTXGeneratorComponent(Component):
    display_name = "PPTX Generator Component"
    description = "Use this component to generate speech draft from a PowerPoint file."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "images"
    name = "PPTXGeneratorComponent"
    inputs = [
        MessageTextInput(name="content", display_name="Content", info="The text content that will be used to generate the PPTX file", required=True),
        MessageTextInput(name="language", display_name="Language", info="The text content that will be used to generate the PPTX file", required=False, value=""),
        MessageTextInput(name="requesting_agent", display_name="Requesting Agent", info="The requesting agent identifier", required=False, value=""),
        # MessageTextInput(name="langfuse_metadata", display_name="Langfuse Metadata", info="User customized metadata that needs to be traced", required=False, value={}),
        # MessageTextInput(name="langfuse_keys", display_name="Langfuse Keys", info="Langfuse public and secret key", required=False, value={}),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}pptx_generator/topic/"
        
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        fields = {
            "content" : self.content,
            "language": self.language,
            "requesting_agent":self.requesting_agent,
            "langfuse_metadata": {},
            "langfuse_keys": {}
        }
        
        response = http.request('POST', url, headers=headers, json=fields)
        
        result = json.loads(response.data.decode('utf-8'))
        
        ppt_uuid = result.get('uuid', "")
        
        if not ppt_uuid:
            data_obj = Data(value=f"Something went wrong")
            self.status = data_obj
        
        while True:
            url_uuid = url + ppt_uuid
            response = http.request('GET', url_uuid, headers=headers, body=url_uuid, preload_content=False)
            
            content_type = response.headers.get('Content-Type')
            # If the response is a file, process it
            if content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                subdirectory = time.strftime("%Y-%m-%d", time.gmtime())
                temp_dir = tempfile.gettempdir()
                full_path = os.path.join(temp_dir, "langflow_temp", subdirectory)
                temp_file_path = os.path.join(full_path, f"presentation-{ppt_uuid}.pptx")
                os.makedirs(full_path, exist_ok=True)
                with open(temp_file_path, 'wb') as f:
                    while True:         
                        data = response.read(1024)         
                        if not data: 
                            break 
                        f.write(data)

                response.release_conn()
                data_obj = Data(value=temp_file_path)
                return data_obj
            else:
                time.sleep(10)
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
        