
from langflow import CustomComponent
from langchain.docstore.document import Document
from typing import Optional
from langchain_community.document_loaders.college_confidential import CollegeConfidentialLoader

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
        documents = CollegeConfidentialLoader(web_path=web_path).load()
        if(metadata):
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
