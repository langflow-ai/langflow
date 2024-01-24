from typing import Dict, List, Optional

from langchain import CustomComponent
from langchain_community.document_loaders import UnstructuredHTMLLoader
from langchain_core.documents import Document


class UnstructuredHTMLLoaderComponent(CustomComponent):
    display_name = "UnstructuredHTMLLoader"
    description = "Load `HTML` files using `Unstructured`."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/how_to/html"

    def build_config(self):
        return {
            "file_path": {"display_name": "File Path", "type": "file", "fileTypes": ["html"]},
            "metadata": {"display_name": "Metadata"},
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> List[Document]:
        # Assuming the existence of a function or class named UnstructuredHTMLLoader that
        # loads HTML and creates a Document object; Replace with actual implementation.
        docs = UnstructuredHTMLLoader(file_path=file_path).load()

        if metadata:
            for doc in docs:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update(metadata)
        return docs
