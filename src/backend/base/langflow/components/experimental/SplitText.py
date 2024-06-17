from typing import List

from langflow.custom import Component
from langflow.inputs import HandleInput, IntInput, TextInput
from langflow.schema import Data
from langflow.template import Output
from langflow.utils.util import unescape_string


class SplitTextComponent(Component):
    display_name: str = "Split Text"
    description: str = "Split text into chunks based on specified criteria."
    icon = "scissors-line-dashed"

    inputs = [
        HandleInput(name="data", display_name="Data", info="Data with text to split.", input_types=["Data"]),
        TextInput(
            name="text_key",
            display_name="Text Key",
            info="The key to access the text content in the Data object.",
            value="text",
        ),
        TextInput(
            name="separator",
            display_name="Separator",
            info='The character to split on. Defaults to "\n".',
            value="\n",
            advanced=True,
        ),
        IntInput(
            name="min_chunk_size",
            display_name="Minimum Chunk Size",
            info="The minimum size of chunks. Smaller chunks will be merged.",
            value=10,
            advanced=True,
        ),
        IntInput(
            name="max_chunk_size",
            display_name="Maximum Chunk Size",
            info="The maximum size of chunks. Larger chunks will be split.",
            value=200,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Chunks", name="chunks", method="split_text"),
    ]

    def split_text(self) -> List[Data]:
        data = self.data if isinstance(self.data, list) else [self.data]
        text_key = self.text_key
        separator = unescape_string(self.separator)
        min_chunk_size = self.min_chunk_size
        max_chunk_size = self.max_chunk_size
        results = []

        if not separator:
            raise ValueError("Separator cannot be empty.")
        if max_chunk_size < 10:
            raise ValueError("Maximum chunk size cannot be less than 10 characters.")
        if min_chunk_size < 10:
            raise ValueError("Minimum chunk size cannot be less than 10 characters.")
        if max_chunk_size < min_chunk_size:
            raise ValueError("Maximum chunk size cannot be less than minimum chunk size.")

        buffer = ""

        for row in data:
            text = row.data.get(text_key, "")
            chunks = text.split(separator)

            for chunk in chunks:
                buffer += chunk
                while len(buffer) >= max_chunk_size:
                    results.append(Data(data={"parent": text, "chunk": buffer[:max_chunk_size]}))
                    buffer = buffer[max_chunk_size:]
                if len(buffer) >= min_chunk_size:
                    results.append(Data(data={"parent": text, "chunk": buffer}))
                    buffer = ""

        # Handle any remaining text that may not meet the min_chunk_size requirement
        if buffer:
            results.append(Data(data={"parent": text, "chunk": buffer}))

        self.status = results
        return results
