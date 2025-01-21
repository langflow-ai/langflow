from langflow.custom import Component
from langflow.io import Output, FileInput
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
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class ParsingFileDiagramExtractorComponent(Component):
    display_name = "Parsing File Diagram Extractor Component"
    description = "Extracts structured data from diagrams."
    icon = "pickaxe"
    name = "DiagramExtractorComponent"
    
    # Define the inputs for extract_data_using_output_parser_file
    inputs = [
        FileInput(name="parsing_file", display_name="Parsing File", file_types=["json"], info="Upload the JSON parsing file.", required=True),
        FileInput(name="image_file_path", display_name="Image", file_types=["jpg", "jpeg", "png", "apng","bmp", "image", "jfif", "avif", "gif", "pjpeg", "pjp", "svg", "webp"], info="Upload the diagram image.", required=True),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Extracted Data", name="extracted_data", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
    
    def build_output_data(self) -> Data:
        with open(self.image_file_path, 'rb') as file1:
            image_content = file1.read()
        with open(self.parsing_file, 'rb') as file2:
            parsing_content = file2.read()

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        url = f"{SDCP_ROOT_URL}diagram_extractor/extract_diagram_with_parser"

        headers = {'accept': 'multipart/form-data'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
            
        # Prepare the fields for multipart/form-data
        fields = {
            'parsing_file':  ('parser.json', parsing_content, "application/json"),
            'image': ('images.jfif', image_content, 'image/jpeg')
        }
        encoded_data, content_type = encode_multipart_formdata(fields)
        headers['Content-Type'] = content_type
 
        response = http.request('POST', url, body=encoded_data, headers=headers)
        
        result = json.loads(response.data.decode('utf-8'))
        extracted_data = result.get("data", {})
        return Data(value=extracted_data)
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
