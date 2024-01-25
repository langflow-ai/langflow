from langflow import CustomComponent
from langflow.field_typing import Document
from typing import Optional, Dict


class TextLoaderComponent(CustomComponent):
    display_name = "TextLoader"
    description = "Load text file."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "type": "file",
                "suffixes": [".txt"],
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "type": "dict",
                "default": {},
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        return Document(file_path=file_path, metadata=metadata)
