import os
import re
import tempfile
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
 
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
import time
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")
 
 
class SharepointDownloadFileFromFileUrlComponent(Component):
    display_name = "Sharepoint Get File by Url"
    description = "Use this component to download a file from sharepoint."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "download"
    name = "SharepointDownloadFileFromFileUrlComponent"

    '''
    drive_name: str = Query("ドキュメント", description="The name of the shared document drive. Defaults to 'ドキュメント' if not provided."),
    file_url: str = Query(..., description="The file url in SharePoint."),
    sharepoint_site_url: str = Query(...,description="The SharePoint site url"),
    access_token: str = Query(..., description="user sharepoint access token"),
    recursive: bool = Query(True, description="Whether to list folder contents recursively. Default is False (top-level only)")
    '''
 
    inputs = [
        MessageTextInput(name="drive_name", display_name="Drive name", placeholder='ドキュメント', required=True, info="The name of the shared document drive. Defaults to 'ドキュメント' if not provided."),
        MessageTextInput(name="file_url", display_name="File Url", required=True, info="The file url in SharePoint."),
        MessageTextInput(name="sharepoint_site_url", display_name="The SharePoint site url", required=True, info="The SharePoint site url."),
        MessageTextInput(name="access_token", display_name="Access token", required=True, info="User's sharepoint access token."),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
   
    def build_output_data(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
 
        url = f"http://{SDCP_ROOT_URL}/sharepoint/get_file_content_by_url/"
        
        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
 
        fields = {
            'drive_name': self.drive_name,
            'file_url': self.file_url,
            'sharepoint_site_url': self.sharepoint_site_url,
            'access_token': self.access_token,
        }
 
        response = http.request('GET', url, headers=headers, fields=fields)

        # Access the 'Content-Disposition' header from the response headers
        content_disposition = response.headers.get('Content-Disposition')

        # Initialize filename variable
        filename = None

        # Check if 'Content-Disposition' header is present
        if content_disposition:
            # Use regular expression to extract the filename
            filename_match = re.search(r'filename="?([^\";]+)"?', content_disposition)
            if filename_match:
                filename = filename_match.group(1)
        
            subdirectory = time.strftime("%Y-%m-%d", time.gmtime())
            temp_dir = tempfile.gettempdir()
            full_path = os.path.join(temp_dir, "langflow_temp", subdirectory)
            temp_file_path = os.path.join(full_path, filename)
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
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
