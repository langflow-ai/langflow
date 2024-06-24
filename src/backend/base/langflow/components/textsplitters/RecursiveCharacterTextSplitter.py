from langchain_text_splitters import RecursiveCharacterTextSplitter

from langflow.custom import Component
from langflow.inputs.inputs import DataInput, IntInput, MessageTextInput
from langflow.schema import Data
from langflow.template.field.base import Output
from langflow.utils.util import build_loader_repr_from_data, unescape_string


class RecursiveCharacterTextSplitterComponent(Component):
    display_name: str = "Recursive Character Text Splitter"
    description: str = "Split text into chunks of a specified length."
    documentation: str = "https://docs.langflow.org/components/text-splitters#recursivecharactertextsplitter"

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
        ),
        MessageTextInput(
            name="separators",
            display_name="Separators",
            info='The characters to split on.\nIf left empty defaults to ["\\n\\n", "\\n", " ", ""].',
            is_list=True,
        ),
    ]
    outputs = [
        Output(display_name="Data", name="data", method="split_data"),
    ]

    def split_data(self) -> list[Data]:
        """
        Split text into chunks of a specified length.

        Args:
            separators (list[str] | None): The characters to split on.
            chunk_size (int): The maximum length of each chunk.
            chunk_overlap (int): The amount of overlap between chunks.

        Returns:
            list[str]: The chunks of text.
        """

        if self.separators == "":
            self.separators: list[str] | None = None
        elif self.separators:
            # check if the separators list has escaped characters
            # if there are escaped characters, unescape them
            self.separators = [unescape_string(x) for x in self.separators]

        # Make sure chunk_size and chunk_overlap are ints
        if self.chunk_size:
            self.chunk_size: int = int(self.chunk_size)
        if self.chunk_overlap:
            self.chunk_overlap: int = int(self.chunk_overlap)
        splitter = RecursiveCharacterTextSplitter(
            separators=self.separators,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        documents = []
        if not isinstance(self.data_input, list):
            self.data_input: list[Data] = [self.data_input]
        for _input in self.data_input:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        docs = splitter.split_documents(documents)
        data = self.to_data(docs)
        self.repr_value = build_loader_repr_from_data(data)
        return data
