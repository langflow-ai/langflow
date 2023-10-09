from typing import Optional
from langflow import CustomComponent
from langchain.schema import Document
from langflow.utils.util import build_loader_repr_from_documents


class RecursiveCharacterTextSplitterComponent(CustomComponent):
    display_name: str = "Recursive Character Text Splitter"
    description: str = "Split text into chunks of a specified length."
    documentation: str = "https://docs.langflow.org/components/text-splitters#recursivecharactertextsplitter"

    def build_config(self):
        return {
            "documents": {
                "display_name": "Documents",
                "info": "The documents to split.",
            },
            "separators": {
                "display_name": "Separators",
                "info": 'The characters to split on.\nIf left empty defaults to ["\\n\\n", "\\n", " ", ""].',
                "is_list": True,
            },
            "chunk_size": {
                "display_name": "Chunk Size",
                "info": "The maximum length of each chunk.",
                "field_type": "int",
                "value": 1000,
            },
            "chunk_overlap": {
                "display_name": "Chunk Overlap",
                "info": "The amount of overlap between chunks.",
                "field_type": "int",
                "value": 200,
            },
            "code": {"show": False},
        }

    def build(
        self,
        documents: list[Document],
        separators: Optional[list[str]] = None,
        chunk_size: Optional[int] = 1000,
        chunk_overlap: Optional[int] = 200,
    ) -> list[Document]:
        """
        Split text into chunks of a specified length.

        Args:
            separators (list[str]): The characters to split on.
            chunk_size (int): The maximum length of each chunk.
            chunk_overlap (int): The amount of overlap between chunks.
            length_function (function): The function to use to calculate the length of the text.

        Returns:
            list[str]: The chunks of text.
        """
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        if separators == "":
            separators = None
        elif separators:
            # check if the separators list has escaped characters
            # if there are escaped characters, unescape them
            separators = [x.encode().decode("unicode-escape") for x in separators]

        # Make sure chunk_size and chunk_overlap are ints
        if isinstance(chunk_size, str):
            chunk_size = int(chunk_size)
        if isinstance(chunk_overlap, str):
            chunk_overlap = int(chunk_overlap)
        splitter = RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        docs = splitter.split_documents(documents)
        self.repr_value = build_loader_repr_from_documents(docs)
        return docs
