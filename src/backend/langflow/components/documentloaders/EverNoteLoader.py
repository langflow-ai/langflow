from langflow import CustomComponent
from langflow.field_typing import Document
from typing import Optional, Dict
from langchain_community.document_loaders.evernote import EverNoteLoader

class EverNoteLoaderComponent(CustomComponent):
    display_name = "EverNoteLoader"
    description = "Load from `EverNote`."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/evernote"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "show": True,
                "type": "file",
                "file_types": [".xml"],
                "field_type": "file",
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "show": True,
                "field_type": "dict",
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        documents = EverNoteLoader(file_path=file_path).load()
        if(metadata):
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
