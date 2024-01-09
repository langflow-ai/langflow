
from langflow import CustomComponent
from langchain.documents import Document
from typing import Optional, Dict

class SRTLoaderComponent(CustomComponent):
    display_name = "SRTLoader"
    description = "Load `.srt` (subtitle) files."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/subtitle"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "fileTypes": ["srt"],
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        return Document(file_path=file_path, metadata=metadata)
