from langflow.custom import Component
from langflow.io import Output, FileInput, MessageTextInput, IntInput
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


class MultiModalQuestionComponent(Component):
    display_name = "Multi-Modal Question Component"
    description = "Perform a search operation."
    icon = "special_components"
    name = "MultiModalQuestionComponent"
    
    # Define the inputs for extract_data_using_output_parser_file
    inputs = [
        FileInput(name="file", display_name="File", file_types=["avif", "bmp", "gif", "ief",  "jpg", "jpe", "jpeg", "heic", "heif", "png", "svg", "tiff", "tif", "ico", "ras", "pnm", "pbm", "pgm", "ppm", "rgb", "xbm", "xpm", "xwd", "pict", "pct", "pic", "webp", "pdf", "docx", "xlsx", "pptx", "m4a", "mp3", "wav"], info="A file to be queried.", required=True),
        MessageTextInput(name="host", display_name="Host", info="Database server host.", required=True),
        IntInput(name="port", display_name="Port", info="Server port.", required=True, value=0),
        MessageTextInput(name="user", display_name="User", info="Database user credentials.", required=True),
        MessageTextInput(name="password", display_name="Password", info="User password.", required=True),
        MessageTextInput(name="db_name", display_name="Db Name", info="Database name.", required=False),
        MessageTextInput(name="collection_name", display_name="Collection Name", info="Name of the new collection to be created.", required=True),
        MessageTextInput(name="query", display_name="Query", info="The query text for searching.", required=True),
        IntInput(name="limit", display_name="Limit", info="Maximum number of results to return.", required=False, value=3),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Extracted Data", name="extracted_data", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
        with open(self.file, 'rb') as file:
            file_content = file.read()

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        url = f"http://{SDCP_ROOT_URL}/multi_modal_question/query/"

        headers = {
          "accept": "application/json",
          "Content-Type": "multipart/form-data"
        }

        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        question_payload = json.dumps({
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "db_name": self.db_name,
            "collection_name": self.collection_name,
            "query": self.query,
            "limit": self.limit,
        })
        fields = {
            "file": ('uploaded_file', file_content, 'application/octet-stream'),
            "question": question_payload
            
        }
        encoded_data, content_type = encode_multipart_formdata(fields)
        headers['Content-Type'] = content_type
 
        response = http.request('POST', url, body=encoded_data, headers=headers)
        
        result = json.loads(response.data.decode('utf-8'))
        extracted_data = result.get("results", [])
        return Data(value=extracted_data)
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)