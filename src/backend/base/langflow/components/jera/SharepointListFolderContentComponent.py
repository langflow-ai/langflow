from langflow.custom import Component
from langflow.io import BoolInput, MessageTextInput, Output
from langflow.schema import Data
import json
 
from langflow.schema.message import Message
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")
 
 
class SharepointListFolderContentComponent(Component):
    display_name = "Sharepoint List Folder Content"
    description = "Use this component to list folder content from sharepoint."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "folders"
    name = "SharepointListFolderContentComponent"

    '''
    drive_name: str = Query("ドキュメント", description="The name of the shared document drive. Defaults to 'ドキュメント' if not provided."),
    folder_path: str = Query("root", description="The path of the folder in SharePoint. Defaults to 'root' if not provided."),
    sharepoint_site_url: str = Query(...,description="The SharePoint site url"),
    access_token: str = Query(..., description="user sharepoint access token"),
    recursive: bool = Query(True, description="Whether to list folder contents recursively. Default is False (top-level only)")
    '''
 
    inputs = [
        MessageTextInput(name="drive_name", display_name="Drive name", placeholder='ドキュメント', required=True, info="The name of the shared document drive. Defaults to 'ドキュメント' if not provided."),
        MessageTextInput(name="folder_path", display_name="Folder path", placeholder='root', required=True, info="The path of the folder in SharePoint. Defaults to 'root' if not provided."),
        MessageTextInput(name="sharepoint_site_url", display_name="The SharePoint site url", required=True, info="The SharePoint site url."),
        MessageTextInput(name="access_token", display_name="Access token", required=True, info="User's sharepoint access token."),
        BoolInput(name="recursive", display_name="recursive", required=True, info="Whether to list folder contents recursively. Default is False (top-level only)"),
    ]
 
    outputs = [
        Output(display_name="Output", name="output", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]
   
    def build_output_data(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
 
        url = f"{SDCP_ROOT_URL}sharepoint/list_folder_content/"
        
        headers = {'accept': 'application/json'}
        if SDCP_TOKEN:
            headers['apikey'] = SDCP_TOKEN
 
        fields = {
            'drive_name': self.drive_name,
            'folder_path': self.folder_path,
            'sharepoint_site_url': self.sharepoint_site_url,
            'access_token': self.access_token,
            'recursive': self.recursive
        }
 
        response = http.request('GET', url, headers=headers, fields=fields)

        response_data = json.loads(response.data.decode('utf-8'))
 
        # Extract the translated text
        folder_content_metadata = response_data["metadata"]
 
        data_obj = Data(value=folder_content_metadata)
        self.status = data_obj
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=iter(self.status.value))
 
 