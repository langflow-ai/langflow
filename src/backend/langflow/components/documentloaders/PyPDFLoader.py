from typing import Dict, List, Optional

from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_core.documents import Document

from langflow import CustomComponent


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
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> List[Document]:
        # Assuming there is a PyPDFLoader class that takes file_path and metadata as parameters
        # and inherits from BaseLoader
        docs = PyPDFLoader(file_path=file_path).load()

        if metadata:
            for doc in docs:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update(metadata)
        return docs
