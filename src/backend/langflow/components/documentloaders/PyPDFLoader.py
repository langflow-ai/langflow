
from langflow import CustomComponent
from langchain.document_loaders import BaseLoader
from typing import Optional, Dict

class PyPDFLoaderComponent(CustomComponent):
    display_name = "PyPDFLoader"
    description = "Load PDF using pypdf into list of documents"
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/how_to/pdf"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "type": "file",
                "fileTypes": ["pdf"],
                "show": True,
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "type": "dict",
                "show": True,
            }
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> BaseLoader:
        # Assuming there is a PyPDFLoader class that takes file_path and metadata as parameters
        # and inherits from BaseLoader
        return PyPDFLoader(file_path=file_path, metadata=metadata)
