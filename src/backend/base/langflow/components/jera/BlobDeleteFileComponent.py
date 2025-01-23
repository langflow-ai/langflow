from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import json
 
import urllib3
import urllib.parse
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")
 
 
class BlobDeleteFileComponent(Component):
    display_name = "Blob delete file Component"
    description = "Use this component to delete file from blob storage."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "BlobDeleteFileComponent"
 
    inputs = [
        MessageTextInput(
            name="file_path",
            display_name="blob path",
            info="The path of the file in blob",
            required=True
        ),
        MessageTextInput(
            name="conn_str",
            display_name="Blob connection string",
            info="The Blob connection string",
            required=True
        ),
        MessageTextInput(
            name="container_name",
            display_name="Blob Container Name",
            info="The blob container name that contains the desired file",
            required=True
        ),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]
 
   
    def build_output(self) -> Data:
       
        file_path = self.file_path
        conn_str = self.conn_str
        container_name = self.container_name
 
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
 
        url = f"{SDCP_ROOT_URL}blob/delete_file/"
        headers = {'accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
 
        fields = {
            "file_path": file_path,
            "conn_str": conn_str,
            "container_name": container_name
        }
        encoded_data = urllib.parse.urlencode(fields)
 
        response = http.request('POST', url, headers=headers, body=encoded_data)
        response_data = json.loads(response.data.decode('utf-8'))
 
        
        return response_data
 
 