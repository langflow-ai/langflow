
from langflow import CustomComponent
from langchain.docstore.document import Document
from typing import Optional

class CollegeConfidentialLoaderComponent(CustomComponent):
    display_name = "CollegeConfidentialLoader"
    description = "Load `College Confidential` webpages."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/college_confidential"

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "values": {}},
            "web_path": {"display_name": "Web Page", "required": True},
        }

    def build(
        self,
        web_path: str,
        metadata: Optional[dict] = {}
    ) -> Document:
        # Assuming there is a loader class `CollegeConfidentialLoader` that takes `metadata` and `web_path` as arguments
        # Replace `CollegeConfidentialLoader` with the actual class name if different
        return CollegeConfidentialLoader(web_path=web_path, metadata=metadata)
