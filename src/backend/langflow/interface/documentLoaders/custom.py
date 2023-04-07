"""Load text files."""
from typing import List

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader


class TextLoader(BaseLoader):
    """Load Text files."""

    def __init__(self, file: str):
        """Initialize with file path."""
        self.file = file

    def load(self) -> List[Document]:
        """Load from file path."""
        documents = [Document(page_content=self.file, metadata={"source": "loaded"})]


CUSTOM_DOCUMENTLOADERS = {
    "TextLoader": TextLoader,
}
