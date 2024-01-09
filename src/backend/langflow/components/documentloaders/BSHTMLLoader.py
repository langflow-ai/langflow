
from langflow import CustomComponent
from langchain.field_typing import Document
from typing import Optional, Dict

class BSHTMLLoaderComponent(CustomComponent):
    display_name = "BSHTMLLoader"
    description = "Load `HTML` files and parse them with `beautiful soup`."
    documentation = "https://python.langchain.com/docs/modules/data_connection/document_loaders/how_to/html"

    def build_config(self):
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "show": True,
                "type": "file",
                "suffixes": [".html"],
                "file_types": ["html"],
            },
            "metadata": {
                "display_name": "Metadata",
                "required": False,
                "show": True,
                "type": "dict",
            },
        }

    def build(self, file_path: str, metadata: Optional[Dict] = None) -> Document:
        # Assuming there is a class or function named BSHTMLLoader that takes a file path and optional metadata
        # and returns a Document object after parsing HTML. Since the actual implementation of BSHTMLLoader is not provided,
        # this is a placeholder and should be replaced with the actual logic.
        raise NotImplementedError("The BSHTMLLoader function or class needs to be implemented.")
