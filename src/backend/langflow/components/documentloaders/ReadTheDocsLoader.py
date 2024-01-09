from langflow import CustomComponent
from langflow.field_typing import Document
from typing import Dict, Optional


class ReadTheDocsLoaderComponent(CustomComponent):
    display_name = "ReadTheDocsLoader"
    description = "Load `ReadTheDocs` documentation directory."

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "default": {}},
            "path": {"display_name": "Local directory", "required": True},
        }

    def build(
        self,
        path: str,
        metadata: Optional[Dict] = None,
    ) -> Document:
        return Document(path=path, metadata=metadata or {})
