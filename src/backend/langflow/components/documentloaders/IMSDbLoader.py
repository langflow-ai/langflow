
from langflow import CustomComponent
from langchain.field_typing import Document
from typing import Dict, Optional

class IMSDbLoaderComponent(CustomComponent):
    display_name = "IMSDbLoader"
    description = "Load `IMSDb` webpages."

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "type": "dict"},
            "web_path": {"display_name": "Web Page", "type": "str"},
        }

    def build(
        self,
        metadata: Optional[Dict] = None,
        web_path: str = "",
    ) -> Document:
        # Assuming there is a class or function named `IMSDbLoader` that takes these parameters
        # and returns a Document object. Replace `IMSDbLoader` with the actual class or function name.
        return IMSDbLoader(metadata=metadata, web_path=web_path)
