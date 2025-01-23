from langflow.custom import Component
from langflow.io import Output, FileInput
from langflow.schema import Data
from langflow.schema.message import Message
import json
import urllib3
from urllib3.util import Retry
from dotenv import load_dotenv
import os

load_dotenv()

SDCP_ROOT_URL = os.getenv("SDCP_ROOT_URL")
SDCP_TOKEN = os.getenv("SDCP_TOKEN")


class DocumentTextExtractorComponent(Component):
    display_name = "Document Text Extractor Component"
    description = "Use this component to extract text from PDF, DOCX, and PPTX files."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "printer"
    name = "DocumentTextExtractorComponent"

    inputs = [
        FileInput(name="document_file_path", display_name="Document File Path", file_types=["pdf", "docx", "pptx"], required=True),
    ]

    outputs = [
        Output(display_name="Data Output", name="output_data", method="build_output_data"),
        Output(display_name="Message Output", name="output_message", method="build_output_message"),
    ]

    def build_output_data(self) -> Data:
        file_path = self.document_file_path
        file_extension = file_path.split('.')[-1].lower()

        # Determine the correct endpoint based on file extension
        if file_extension == 'pdf':
            url = f"{SDCP_ROOT_URL}document_loader/pdf/"
            mime_type = 'application/pdf'
        elif file_extension == 'docx':
            url = f"{SDCP_ROOT_URL}document_loader/docx/"
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif file_extension == 'pptx':
            url = f"{SDCP_ROOT_URL}document_loader/pptx/"
            mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        else:
            raise ValueError("Unsupported file type")

        with open(file_path, 'rb') as file:
            file_content = file.read()

            http = urllib3.PoolManager(retries=Retry(total=3, backoff_factor=0.2))

            headers = {'accept': 'application/json'}
            if SDCP_TOKEN:
                headers['apikey'] = SDCP_TOKEN

            fields = {'file': (file_path, file_content, mime_type)}
            response = http.request('POST', url, headers=headers, fields=fields)
            result = json.loads(response.data.decode('utf-8'))

            # Extract the page content
            file_content = "".join(page["page_content"] for page in result["docs"])
            data_obj = Data(value=file_content)
        return data_obj
        
    def build_output_message(self) -> Message:
        return Message(text=self.build_output_data().value)
