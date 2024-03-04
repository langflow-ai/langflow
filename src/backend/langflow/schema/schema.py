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

    text: Optional[str] = ""
    data: dict = {}

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
            str: The text and data of the record.
        """
        return self.model_dump_json(indent=2)
