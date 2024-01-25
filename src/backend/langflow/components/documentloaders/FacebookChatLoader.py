from langflow import CustomComponent
from langchain.docstore.document import Document
from typing import List, Optional, Dict
from langchain_community.document_loaders.facebook_chat import FacebookChatLoader


class FacebookChatLoaderComponent(CustomComponent):
    display_name = "FacebookChatLoader"
    description = "Load `Facebook Chat` messages directory dump."
    documentation = (
        "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/facebook_chat"
    )

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "file_types": [".json"],
                "field_type": "file",
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "field_type": "dict",
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> List[Document]:
        documents = FacebookChatLoader(path=file_path).load()
        if metadata:
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
