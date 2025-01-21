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
SDCP_TOKEN = os.getenv("SDCP_ROOT_URL")


class BlobGetDownloadURLComponent(Component):
    display_name = "Blob get download url Component"
    description = "Use this component to get the download url of a file from blob storage."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "special_components"
    name = "BlobGetDownloadURLComponent"

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
        MessageTextInput(
            name="expiry_hours",
            display_name="expiration hours for the url",
            info="The number of hours for which the download URL will remain valid",
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
        expiry_hours = self.expiry_hours

        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

        url = f"http://{SDCP_ROOT_URL}/blob/download-url/"
        headers = {'accept': 'application/json'}

        fields = {
            "file_path": file_path,
            "conn_str": conn_str,
            "container_name": container_name,
            "expiry_hours": expiry_hours
        }
        encoded_data = urllib.parse.urlencode(fields)
        full_url = f"{url}?{encoded_data}"

        response = http.request('GET', full_url, headers=headers)
        response_data = json.loads(response.data.decode('utf-8'))

        return response_data