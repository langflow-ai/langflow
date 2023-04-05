"""Load text files."""
from typing import List

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader
from langchain.text_splitter import CharacterTextSplitter


class Text(BaseLoader):
    """Load Text files."""

    def __init__(self, file: str):
        """Initialize with file path."""
        self.file = file

    def load(self) -> List[Document]:
        """Load from file path."""
        documents = [Document(page_content=self.file, metadata={"source": "loaded"})]

        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)

        return text_splitter.split_documents(documents)


CUSTOM_DOCUMENTLOADERS = {
    "Text": Text,
}
