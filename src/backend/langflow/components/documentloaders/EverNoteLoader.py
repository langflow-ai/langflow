
from langflow import CustomComponent
from langchain.field_typing import Document
from typing import Optional, Dict

class EverNoteLoaderComponent(CustomComponent):
    display_name = "EverNoteLoader"
    description = "Load from `EverNote`."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/evernote"
    
    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "suffixes": [".xml"],
                "show": True,
                "type": "file",
                "file_types": ["xml"],
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "show": True,
                "type": "dict",
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        # Assuming there is a function or class named `EverNoteLoader` that takes these parameters
        # and returns a `Document` object. Replace `EverNoteLoader` with the actual implementation.
        return EverNoteLoader(file_path=file_path, metadata=metadata)
