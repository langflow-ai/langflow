from langflow.custom import Component
from langflow.io import MessageTextInput, Output, FileInput
from langflow.schema import Data
import json
import urllib3
from urllib3.util import Retry
from urllib3.filepost import encode_multipart_formdata
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class UserQueryExtractorComponent(Component):
    display_name = "User Query Extractor Component"
    description = "Extract structured data based on user query and diagram."
    icon = "special_components"
    name = "UserQueryExtractorComponent"
    
    # Define the inputs for extract_structured_data_based_on_user_query
    inputs = [
        MessageTextInput(name="user_query", display_name="User Query", info="Enter the user query for extraction.", required=True),
        FileInput(name="image_file_path", display_name="Image", file_types=["jpg", "jpeg", "png", "apng","bmp", "image", "jfif", "avif", "gif", "pjpeg", "pjp", "svg", "webp"], info="Upload the diagram image.", required=True),
    ]
    
    # Define the output
    outputs = [
        Output(display_name="Extracted Data", name="extracted_data", method="build_output"),
    ]
    
    def build_output(self) -> Data:
        with open(self.image_file_path, 'rb') as file:
            file_content = file.read()
        user_query = self.user_query

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        url = f"{SDCP_ROOT_URL}diagram_extractor/extract_diagram_with_description"
        headers = {'accept': 'multipart/form-data'}
        # Prepare the fields for multipart/form-data
        fields = {
            "user_query": user_query,
            'image': ('images.jfif', file_content, 'image/jpeg')
        }
        encoded_data, content_type = encode_multipart_formdata(fields)
        headers['Content-Type'] = content_type
 
        response = http.request('POST', url, body=encoded_data, headers=headers)

        result = json.loads(response.data.decode('utf-8'))
        
        extracted_data = result.get("data", {})
        return Data(value=extracted_data)