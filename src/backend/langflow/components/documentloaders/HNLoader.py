from langflow import CustomComponent
from typing import List, Optional, Dict
from langchain_community.document_loaders.hn import HNLoader
from langflow.field_typing import Document


class HNLoaderComponent(CustomComponent):
    display_name = "HNLoader"
    description = "Load `Hacker News` data."

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "value": {}, "required": False, "field_type": "dict"},
            "web_path": {"display_name": "Web Page", "required": True},
        }

    def build(
        self,
        web_path: str,
        metadata: Optional[Dict] = None,
    ) -> List[Document]:
        documents = HNLoader(web_path=web_path).load()
        if metadata:
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
