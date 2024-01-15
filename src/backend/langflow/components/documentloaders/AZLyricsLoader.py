from langflow import CustomComponent
from langflow.field_typing import Document
from typing import Optional, Dict
from langchain_community.document_loaders.azlyrics import AZLyricsLoader


class AZLyricsLoaderComponent(CustomComponent):
    display_name = "AZLyricsLoader"
    description = "Load `AZLyrics` webpages."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/azlyrics"

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "field_type": "dict", "value": {}, "show": True},
            "web_path": {"display_name": "Web Page", "type": "str", "required": True, "show": True},
        }

    def build(self, metadata: Optional[Dict] = None, web_path: str = "") -> Document:
        documents = AZLyricsLoader(web_path=web_path).load()
        if(metadata):
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents