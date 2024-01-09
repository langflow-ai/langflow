
from langchain import CustomComponent
from langchain.field_typing import Document
from typing import Optional, Dict


class UnstructuredWordDocumentLoaderComponent(CustomComponent):
    display_name = "UnstructuredWordDocumentLoader"
    description = "Load `Microsoft Word` file using `Unstructured`."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/integrations/microsoft_word"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "type": "file",
                "suffixes": [".docx", ".doc"],
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "type": "dict"
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        return Document(file_path=file_path, metadata=metadata)
