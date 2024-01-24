from langflow import CustomComponent
from langflow.field_typing import Document
from typing import Optional, Dict
from langchain_community.document_loaders.gitbook import GitbookLoader


class GitbookLoaderComponent(CustomComponent):
    display_name = "GitbookLoader"
    description = "Load `GitBook` data."

    def build_config(self):
        return {
            "metadata": {
                "display_name": "Metadata",
                "field_type": "dict",
                "value": {},
            },
            "web_page": {
                "display_name": "Web Page",
                "required": True,
            },
        }

    def build(self, metadata: Optional[Dict] = None, web_page: str = "") -> Document:
        documents = GitbookLoader(web_page=web_page).load()
        if metadata:
            for document in documents:
                if not document.metadata:
                    document.metadata = metadata
                else:
                    document.metadata.update(metadata)
        return documents
