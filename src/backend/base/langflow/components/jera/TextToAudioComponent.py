from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema.message import Message
from langflow.schema import Data

import tempfile 
import json
import os
import uuid
import urllib3
from urllib3.util import Retry
from time import gmtime, strftime
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class TextToAudioComponent(Component):
    display_name = "Text To Audio Component"
    description = "convert text to audio"
    icon = "file-audio-2"
    name = "TextToAudioComponent"

    inputs = [
        DataInput(name="data_input", display_name="Data", info="The data to convert to text."),
         
    ]
    
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]

    def build_output_data(self) -> Message:
        text_audio = self.data_input.value if isinstance(self.data_input, Data) else {}

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"{SDCP_ROOT_URL}audio_generator/generate-audio/"
        
        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN

        fields = json.dumps({"text": text_audio,"voice": "alloy","response_format": "mp3","speed": 1}).encode('utf-8')
        response = http.request('POST', url, headers=headers, body=fields, preload_content=False)
        # response = http.request('POST', url, headers=headers, body=fields)
        subdirectory = strftime("%Y-%m-%d", gmtime())
        temp_dir = tempfile.gettempdir()
        full_path = os.path.join(temp_dir, "langflow_temp", subdirectory)
        file_uuid = uuid.uuid4()        
        temp_file_path = os.path.join(full_path, f"audio-{file_uuid}.mp3")
        os.makedirs(full_path, exist_ok=True)
        with open(temp_file_path, 'wb') as f:
            while True:         
                data = response.read(1024)         
                if not data: 
                    break 
                f.write(data)
        response.release_conn()
            # f.write(response.data)

        data_obj = Data(value=temp_file_path)
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
