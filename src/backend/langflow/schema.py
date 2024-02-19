from typing import Any, Optional

from langchain_core.documents import Document
from pydantic import BaseModel


class Record(BaseModel):
    """
    Represents a record with text and optional data.

    Attributes:
        text (str): The text of the record.
        data (dict, optional): Additional data associated with the record.
    """

    text: str
    data: Optional[dict] = None

    @classmethod
    def from_document(cls, document: Document) -> "Record":
        """
        Converts a Document to a Record.

        Args:
            document (Document): The Document to convert.

        Returns:
            Record: The converted Record.
        """
        return cls(text=document.page_content, data=document.metadata)

    def to_lc_document(self) -> Document:
        """
        Converts the Record to a Document.

        Returns:
            Document: The converted Document.
        """
        return Document(page_content=self.text, metadata=self.data)

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        """
        Returns the text of the record.

        Returns:
            Any: The text of the record.
        """
        return self.text

    def __str__(self) -> str:
        """
        Returns the text of the record.

        Returns:
            str: The text of the record.
        """
        return self.text


def docs_to_records(documents: list[Document]) -> list[Record]:
    """
    Converts a list of Documents to a list of Records.

    Args:
        documents (list[Document]): The list of Documents to convert.

    Returns:
        list[Record]: The converted list of Records.
    """
    return [Record.from_document(document) for document in documents]
