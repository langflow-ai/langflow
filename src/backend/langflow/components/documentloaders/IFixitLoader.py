from typing import Dict, List, Optional

from langchain_community.document_loaders.ifixit import IFixitLoader
from langflow import CustomComponent
from langflow.field_typing import Document


class IFixitLoaderComponent(CustomComponent):
    display_name = "IFixitLoader"
    description = "Load `iFixit` repair guides, device wikis and answers."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/ifixit"

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "type": "dict", "default": {}},
            "web_path": {"display_name": "Web Page", "type": "str"},
        }

    def build(self, web_path: str, metadata: Optional[Dict] = None) -> List[Document]:
        # Assuming IFixitLoader is the correct class name from the langchain library,
        # and it has a load method that returns a Document object.
        if metadata is None:
            metadata = {}

        docs = IFixitLoader(web_path=web_path).load()

        if metadata:
            for doc in docs:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update(metadata)
        return docs
