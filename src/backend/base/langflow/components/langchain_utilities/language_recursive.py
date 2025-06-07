from typing import Any

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter, TextSplitter

from langflow.base.textsplitters.model import LCTextSplitterComponent
from langflow.inputs.inputs import DataInput, DropdownInput, IntInput


class LanguageRecursiveTextSplitterComponent(LCTextSplitterComponent):
    display_name: str = "Language Recursive Text Splitter"
    description: str = "Split text into chunks of a specified length based on language."
    documentation: str = "https://docs.langflow.org/components/text-splitters#languagerecursivetextsplitter"
    name = "LanguageRecursiveTextSplitter"
    icon = "LangChain"

    inputs = [
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="The maximum length of each chunk.",
            value=1000,
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk Overlap",
            info="The amount of overlap between chunks.",
            value=200,
        ),
        DataInput(
            name="data_input",
            display_name="Input",
            info="The texts to split.",
            input_types=["Document", "Data"],
            required=True,
        ),
        DropdownInput(
            name="code_language", display_name="Code Language", options=[x.value for x in Language], value="python"
        ),
    ]

    def get_data_input(self) -> Any:
        return self.data_input

    def build_text_splitter(self) -> TextSplitter:
        return RecursiveCharacterTextSplitter.from_language(
            language=Language(self.code_language),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
