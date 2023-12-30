from langflow import CustomComponent
from langflow.utils.constants import LOADERS_INFO
from langflow.field_typing import Object

from llama_index.readers import SimpleDirectoryReader


class SimpleDirectoryReaderComponent(CustomComponent):
    display_name: str = "Simple Directory Reader (LlamaIndex)"
    description: str = "Directory reader for llamaindex"
    beta = True

    def build_config(self):
        """Build config."""
        return {
            "file_path": {
                "display_name": "File Path",
                "required": True,
                "field_type": "file",
                "file_types": [
                    "hwp",
                    "pdf",
                    "docx",
                    "pptx",
                    "ppt",
                    "pptm",
                    "jpg",
                    "png",
                    "jpeg",
                    "mp3",
                    "mp4",
                    "csv",
                    "epub",
                    "md",
                    "mbox",
                    "ipynb",
                    "txt",
                ],
                "suffixes": [
                    ".hwp",
                    ".pdf",
                    ".docx",
                    ".pptx",
                    ".ppt",
                    ".pptm",
                    ".jpg",
                    ".png",
                    ".jpeg",
                    ".mp3",
                    ".mp4",
                    ".csv",
                    ".epub",
                    ".md",
                    ".mbox",
                    ".ipynb",
                    ".txt"
                ],
            },
            "code": {"show": False},
        }

    def build(self, file_path: str) -> Object:
        """Build."""
        
        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()

        # returns a list of documents
        return documents
