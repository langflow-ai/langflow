# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import urllib3
from urllib3.util import Retry
import json
from dotenv import load_dotenv
import os

load_dotenv()


SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class FilesUploadEmbeddingStatusComponent(Component):
    display_name = "Upload File Component"
    description = "Use this component to get the embedding status of a specific task."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "notebook-pen"
    name = "FilesUploadEmbeddingStatusComponent"

    inputs = [
        MessageTextInput(name="task_id", display_name="Task ID", info="The task ID that is going to be status checked", required=True),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))
        
        task_id = self.task_id
        url = f"{SDCP_ROOT_URL}blob/files_upload_embedding_status/{task_id}"

        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}


        response = http.request('GET', url, headers=headers)
        
        result = json.loads(response.data.decode('utf-8'))
        return Data(value=result.get("message", ""))