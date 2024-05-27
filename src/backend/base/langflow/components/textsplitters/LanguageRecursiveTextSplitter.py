from typing import List, Optional

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from langflow.custom import CustomComponent
from langflow.schema.schema import Record


class LanguageRecursiveTextSplitterComponent(CustomComponent):
    display_name: str = "Language Recursive Text Splitter"
    description: str = "Split text into chunks of a specified length based on language."
    documentation: str = "https://docs.langflow.org/components/text-splitters#languagerecursivetextsplitter"

    def build_config(self):
        options = [x.value for x in Language]
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "separator_type": {
                "display_name": "Separator Type",
                "info": "The type of separator to use.",
                "field_type": "str",
                "options": options,
                "value": "Python",
            },
            "separators": {
                "display_name": "Separators",
                "info": "The characters to split on.",
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
        inputs: List[Record],
        chunk_size: Optional[int] = 1000,
        chunk_overlap: Optional[int] = 200,
        separator_type: str = "Python",
    ) -> list[Record]:
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

        # Make sure chunk_size and chunk_overlap are ints
        if isinstance(chunk_size, str):
            chunk_size = int(chunk_size)
        if isinstance(chunk_overlap, str):
            chunk_overlap = int(chunk_overlap)

        splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language(separator_type),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        documents = []
        for _input in inputs:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        docs = splitter.split_documents(documents)
        records = self.to_records(docs)
        return records
