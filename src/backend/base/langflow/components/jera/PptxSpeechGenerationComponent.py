import os
import tempfile
from langflow.custom import Component
from langflow.inputs.inputs import DataInput
from langflow.io import Output, FileInput, MessageTextInput
from langflow.schema import Data
import json
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from urllib3.filepost import encode_multipart_formdata
import time
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class PptxSpeechGenerationComponent(Component):
    display_name = "PPTX Speech Generation Component"
    description = "Use this component to generate speech draft from a PowerPoint file."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "speech"
    name = "PptxSpeechGenerationComponent"
    inputs = [
        FileInput(name="pptx_file_path", display_name="PPTX File Path", file_types=["pptx", "ppt"]),
        DataInput(name="data_file_path_input", display_name="Data File Path", info="The data to convert to text."),
        MessageTextInput(name="message", display_name="Message", info="The original user query", required=True),
        MessageTextInput(name="requesting_agent", display_name="Requesting Agent", info="The requesting agent identifier", required=True),
        # MessageTextInput(name="langfuse_metadata", display_name="Langfuse Metadata", info="User customized metadata that needs to be traced", required=False, value=""),
        # MessageTextInput(name="langfuse_keys", display_name="Langfuse Keys", info="Langfuse public and secret key", required=False, value=""),
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]

    def build_output_data(self) -> Data:
        data_file_path = self.data_file_path_input.value if isinstance(self.data_file_path_input, Data) else {}
        
        if not data_file_path:
            data_file_path = self.pptx_file_path
        
        if not data_file_path:
            raise Exception("File path is required")
        
        with open(data_file_path, 'rb') as file:
            file_content = file.read()
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}speech_generation/ppt-document/"

        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        fields = {
            "message": self.message,
            "file": ('presentation.pptx', file_content, 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
            "requesting_agent":self.requesting_agent,
            "langfuse_metadata": json.dumps({}),
            "langfuse_keys": json.dumps({})
        }

        encoded_data, content_type = encode_multipart_formdata(fields)
        headers['Content-Type'] = content_type
 
        response = http.request('POST', url, body=encoded_data, headers=headers)

        result = json.loads(response.data.decode('utf-8'))

        draft_uuid = result.get('draft_uuid', "")
        
        if not draft_uuid:
            data_obj = Data(value=f"Something went wrong")
            self.status = data_obj

        while True:
            url_uuid = url + draft_uuid
            response = http.request('GET', url_uuid, headers=headers, body=url_uuid, preload_content=False)
            
            content_type = response.headers.get('Content-Type')
            # If the response is a file, process it
            if content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
                subdirectory = time.strftime("%Y-%m-%d", time.gmtime())
                temp_dir = tempfile.gettempdir()
                full_path = os.path.join(temp_dir, "langflow_temp", subdirectory)
                temp_file_path = os.path.join(full_path, f"presentation-{draft_uuid}.pptx")
                os.makedirs(full_path, exist_ok=True)
                with open(temp_file_path, 'wb') as f:
                    while True:         
                        data = response.read(1024)         
                        if not data: 
                            break 
                        f.write(data)

                response.release_conn()
                data_obj = Data(value=f"{temp_file_path} --- {content_type}")
                return data_obj
            else:
                time.sleep(10)
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
