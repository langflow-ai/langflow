
from langflow import CustomComponent
from langchain.docstore.document import Document
from typing import Optional, Dict

class FacebookChatLoaderComponent(CustomComponent):
    display_name = "FacebookChatLoader"
    description = "Load `Facebook Chat` messages directory dump."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/facebook_chat"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "suffixes": [".json"],
                "file_types": ["json"],
                "field_type": "file",
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "field_type": "dict",
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        # Assuming there is a class named FacebookChatLoader that takes file_path and metadata as parameters
        # and returns a Document object. Replace 'FacebookChatLoader' with the actual class name.
        # As per the JSON, the output type is 'Document', which is part of langchain.documents.
        # Therefore, the 'FacebookChatLoader' should be imported or defined elsewhere in the codebase.
        return FacebookChatLoader(file_path=file_path, metadata=metadata)