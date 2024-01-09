
from langflow import CustomComponent
from langchain.documents import Document
from typing import Optional, Dict

class PyPDFDirectoryLoaderComponent(CustomComponent):
    display_name = "PyPDFDirectoryLoader"
    description = "Load a directory with `PDF` files using `pypdf` and chunks at character level."

    def build_config(self):
        return {
            "metadata": {"display_name": "Metadata", "required": False},
            "path": {"display_name": "Local directory", "required": True},
        }

    def build(
        self,
        path: str,
        metadata: Optional[Dict] = None,
    ) -> Document:
        # Assuming there is a PyPDFDirectoryLoader class that takes these parameters
        # Since the actual implementation is not provided, this is a placeholder
        return PyPDFDirectoryLoader(path=path, metadata=metadata)
