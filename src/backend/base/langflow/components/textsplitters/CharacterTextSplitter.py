from typing import List

from langchain_text_splitters import CharacterTextSplitter

from langflow.custom import CustomComponent
from langflow.schema import Data
from langflow.utils.util import unescape_string


class CharacterTextSplitterComponent(CustomComponent):
    display_name = "CharacterTextSplitter"
    description = "Splitting text that looks at characters."

    def build_config(self):
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Data"]},
            "chunk_overlap": {"display_name": "Chunk Overlap", "default": 200},
            "chunk_size": {"display_name": "Chunk Size", "default": 1000},
            "separator": {"display_name": "Separator", "default": "\n"},
        }

    def build(
        self,
        inputs: List[Data],
        chunk_overlap: int = 200,
        chunk_size: int = 1000,
        separator: str = "\n",
    ) -> List[Data]:
        # separator may come escaped from the frontend
        separator = unescape_string(separator)
        documents = []
        for _input in inputs:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        docs = CharacterTextSplitter(
            chunk_overlap=chunk_overlap,
            chunk_size=chunk_size,
            separator=separator,
        ).split_documents(documents)
        data = self.to_data(docs)
        self.status = data
        return data
