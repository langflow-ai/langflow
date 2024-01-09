from langchain import CustomComponent
from langflow.field_typing import Document
from typing import Optional, Dict


class UnstructuredHTMLLoaderComponent(CustomComponent):
    display_name = "UnstructuredHTMLLoader"
    description = "Load `HTML` files using `Unstructured`."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/how_to/html"

    def build_config(self):
        return {
            "file_path": {"display_name": "File Path", "type": "file", "fileTypes": ["html"]},
            "metadata": {"display_name": "Metadata"},
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        # Assuming the existence of a function or class named UnstructuredHTMLLoader that
        # loads HTML and creates a Document object; Replace with actual implementation.
        return UnstructuredHTMLLoader(file_path=file_path, metadata=metadata)
