from langflow import CustomComponent
from langflow.field_typing import Document
from langchain_community.document_loaders.imsdb import IMSDbLoader

from typing import Dict, Optional


class IMSDbLoaderComponent(CustomComponent):
    display_name = "IMSDbLoader"
    description = "Load `IMSDb` webpages."

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "field_type": "dict"},
            "web_path": {"display_name": "Web Page", "field_type": "str"},
        }

    def build(
        self,
        metadata: Optional[Dict] = None,
        web_path: str = "",
    ) -> Document:
        return IMSDbLoader(metadata=metadata, web_path=web_path)
