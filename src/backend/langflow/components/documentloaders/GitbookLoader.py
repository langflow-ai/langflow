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
                "field_type":"dict",
                "value": {},
            },
            "web_page": {
                "display_name": "Web Page",
                "required": True,
            },
        }

    def build(self, metadata: Optional[Dict] = None, web_page: str = "") -> Document:
        # Assuming there is a GitbookLoader class that takes metadata and web_page as parameters
        # Replace 'GitbookLoader' with the actual class name if different
        return GitbookLoader(metadata=metadata, web_page=web_page)
