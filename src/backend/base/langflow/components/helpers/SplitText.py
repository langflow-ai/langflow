from typing import Optional

from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
)
from langchain_core.documents import Document

from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema import Record
from langflow.field_typing import Text
from langflow.utils.util import unescape_string


class SplitTextComponent(CustomComponent):
    display_name: str = "Split Text"
    description: str = "Split text into chunks of a specified length."

    def build_config(self):
        return {
            "texts": {
                "display_name": "Texts",
                "info": "Texts to split.",
                "input_types": ["Text"],
            },
            "separators": {
                "display_name": "Separators",
                "info": 'The characters to split on.\nIf left empty defaults to [" "].',
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
            "recursive": {
                "display_name": "Recursive",
            },
            "code": {"show": False},
        }

    def build(
        self,
        texts: list[Text],
        separators: Optional[list[str]] = [" "],
        chunk_size: Optional[int] = 1000,
        chunk_overlap: Optional[int] = 200,
        recursive: bool = False,
    ) -> list[Record]:
        separators = [unescape_string(x) for x in separators]

        # Make sure chunk_size and chunk_overlap are ints
        if isinstance(chunk_size, str):
            chunk_size = int(chunk_size)
        if isinstance(chunk_overlap, str):
            chunk_overlap = int(chunk_overlap)

        if recursive:
            splitter = RecursiveCharacterTextSplitter(
                separators=separators,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        else:
            splitter = CharacterTextSplitter(
                separator=separators[0],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

        documents = []
        for _text in texts:
            # documents.append(_input.to_lc_document())
            documents.append(Document(page_content=_text))

        records = self.to_records(splitter.split_documents(documents))
        self.status = records
        return records
